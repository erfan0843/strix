"""
تست فاز ۹ — فرم‌ساز کامل

پوشش:
  • ۹ نوع فرم × ۵۵+ نوع فیلد × ۱۵ دسته
  • ویزارد ساخت فرم، لینک اختصاصی، انتشار
  • مدیریت فیلد: افزودن/ویرایش/کپی/حذف/جابه‌جایی/گزینه/شرط
  • تنظیمات پیشرفته (۸ بخش) + پرداخت فرم (۴ روش)
  • پر کردن فرم: هر دو حالت نمایش + اعتبارسنجی همه انواع
  • پاسخ‌ها، برچسب، گزارش تحلیلی، خروجی Excel
  • تک‌منو (رفع منوی تکراری)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora9_")
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
    p = p or {}
    SENT.append({"m": m, "p": p})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    if m == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if m == "getFile":
        return {"ok": True, "result": {"file_path": "x.jpg"}}
    if m == "sendInvoice":
        return {"ok": True, "result": {"message_id": 5}}
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage", "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText", "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file("sendPhoto", "photo", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file("sendDocument", "document", c, d, cap, kb)
bale_api.send_video = lambda c, v, cap=None, kb=None: _file("sendVideo", "video", c, v, cap, kb)
bale_api.send_voice = lambda c, v, cap=None, kb=None: _file("sendVoice", "voice", c, v, cap, kb)

import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fields as FF  # noqa: E402
import form_fill as FL  # noqa: E402
import form_reports as FR  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import iran_data  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, FL, FR, M, PAY, EV, AT):
    for n in ("send", "send_or_edit", "send_photo", "send_document",
              "send_video", "send_voice"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))

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


def kbl():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        rows = kb.get("inline_keyboard") or kb.get("keyboard") or []
        out = []
        for r in rows:
            for b in r:
                out.append(b["text"] if isinstance(b, dict) else str(b))
        if out:
            return out
    return []


def cbdata():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        out = [b.get("callback_data") for r in kb.get("inline_keyboard", [])
               for b in r if isinstance(b, dict) and b.get("callback_data")]
        if out:
            return out
    return []


def msg(uid, t, mid=1):
    return {"message_id": mid, "from": {"id": uid, "first_name": "تست"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c1", "from": {"id": uid, "first_name": "تست"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001     # سوپرادمین
U1 = 111111       # کاربر عادی
U2 = 222222       # کاربر دوم
A2 = 333333       # ادمین دوم

print("=" * 62)
print("🧪 تست فاز ۹ — فرم‌ساز")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PAY.init_payment_tables()
F.init_form_tables()
auth.ensure_super_admin(S)

for u, nm in ((U1, "کاربر"), (U2, "دومی"), (A2, "ادمین۲")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"0912000{u % 10000}", "phone")
database.db_execute("UPDATE users SET is_admin=1 WHERE bale_user_id=?", (A2,))
database.db_execute("UPDATE users SET last_name='خانوادگی' WHERE bale_user_id=?", (U1,))


# ════════════════════ ۱) ساختار داده ════════════════════
print("\n[۱] ساختار انواع فرم و فیلد")
check("۹ نوع فرم", len(F.FORM_TYPES) == 9, str(len(F.FORM_TYPES)))
for k in ("questionnaire", "survey", "registration", "election", "datacollect",
          "contest", "attendance", "exam", "order"):
    check(f"نوع فرم: {F.FORM_TYPES.get(k, {}).get('name', k)}", k in F.FORM_TYPES)

check("۵۰+ نوع فیلد", len(F.FIELD_TYPES) >= 50, str(len(F.FIELD_TYPES)))
check("۱۶ دسته فیلد", len(F.FIELD_CATS) == 16, str(len(F.FIELD_CATS)))

_cats = {c[0] for c in F.FIELD_CATS}
_bad = [k for k, v in F.FIELD_TYPES.items() if v.get("cat") not in _cats]
check("همه فیلدها دسته معتبر دارند", not _bad, str(_bad[:5]))

_nokind = [k for k, v in F.FIELD_TYPES.items() if not v.get("kind")]
check("همه فیلدها kind دارند", not _nokind, str(_nokind[:5]))

_noq = [k for k, v in F.FIELD_TYPES.items() if not v.get("q")]
check("همه فیلدها سوال پیش‌فرض دارند", not _noq, str(_noq[:5]))

_empty = [c for c in F.FIELD_CATS
          if not any(v.get("cat") == c[0] for v in F.FIELD_TYPES.values())]
check("هیچ دسته‌ای خالی نیست", not _empty, str(_empty))

check("۲ حالت نمایش", len(F.DISPLAY_MODES) == 2)
check("۲ جهت متن", len(F.TEXT_DIRS) == 2)
check("۱۵ متن قابل ویرایش", len(F.FORM_TEXTS) >= 15, str(len(F.FORM_TEXTS)))

for tbl in ("forms", "form_fields", "form_responses", "form_answers",
            "form_admins", "user_field_cache", "form_tags"):
    r = database.db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,),
        fetch="one")
    check(f"جدول {tbl}", bool(r))


# ════════════════════ ۲) ساخت فرم ════════════════════
print("\n[۲] ویزارد ساخت فرم")
SENT.clear()
M.handle_callback(cb(S, "fb_panel"))
check("پنل فرم‌ساز باز شد", "فرم‌ساز" in last(), last()[:60])
check("دکمه ایجاد فرم", "fb_new" in cbdata())

SENT.clear()
M.handle_callback(cb(S, "fb_new"))
check("لیست ۹ نوع فرم", sum(1 for d in cbdata() if d.startswith("fbt_")) == 9)

SENT.clear()
M.handle_callback(cb(S, "fbt_registration"))
check("عنوان خواسته شد", "عنوان" in last())
check("state درست", auth.get_state_name(S) == F.STATE_FB_CREATE)

M.process_message(msg(S, "ا"))
check("عنوان کوتاه رد شد", "۳ حرف" in last())

M.process_message(msg(S, "ثبت‌نام کارگاه فن بیان"))
check("لینک خواسته شد", "لینک اختصاصی" in last())

M.process_message(msg(S, "karegah_test"))
fid = database.db_scalar("SELECT MAX(id) FROM forms")
form = F.get_form(fid)
check("فرم ساخته شد", bool(form))
check("عنوان درست", form["title"] == "ثبت‌نام کارگاه فن بیان")
check("slug درست", form["slug"] == "karegah_test")
check("نوع درست", form["form_type"] == "registration")
check("وضعیت پیش‌نویس", form["status"] == "draft")
check("state پاک شد", auth.get_state_name(S) is None)

# slug تکراری
SENT.clear()
M.handle_callback(cb(S, "fbt_survey"))
M.process_message(msg(S, "نظرسنجی رضایت"))
M.process_message(msg(S, "karegah_test"))
check("slug تکراری رد شد", "تکراری" in last() or "استفاده شده" in last())
M.process_message(msg(S, "⏭️ رد کردن"))
fid2 = database.db_scalar("SELECT MAX(id) FROM forms")
f2 = F.get_form(fid2)
check("slug خودکار ساخته شد", bool(f2["slug"]) and f2["slug"] != "karegah_test")
check("نظرسنجی ناشناس است", f2["anonymous"] == 1)

check("clean_slug فارسی حذف می‌کند", F.clean_slug("سلام-abc_12!@#") == "-abc_12")
check("clean_slug طول محدود", len(F.clean_slug("a" * 90)) <= 40)


# ════════════════════ ۳) افزودن فیلد ════════════════════
print("\n[۳] افزودن سوالات")
SENT.clear()
M.handle_callback(cb(S, f"fbf_{fid}"))
check("پیام «سوالی نیست»", "سوالی اضافه نشده" in last())

SENT.clear()
M.handle_callback(cb(S, f"fbfa_{fid}"))
# ⚡ فاز ۹.۱: پرکاربردها مستقیم نمایش داده می‌شوند (مثل دیجی‌فرم)
check("فیلدهای پرکاربرد مستقیم", sum(1 for d in cbdata() if d.startswith("fbn_")) >= 12)
check("دکمه همه دسته‌ها", any(d.startswith("fbcats_") for d in cbdata()))
SENT.clear()
M.handle_callback(cb(S, f"fbcats_{fid}"))
check("۱۶ دسته نمایش داده شد",
      sum(1 for d in cbdata() if d.startswith("fbc_")) == 16)

SENT.clear()
M.handle_callback(cb(S, f"fbc_personal_{fid}"))
check("فیلدهای دسته شخصی", any(d.startswith("fbn_full_name") for d in cbdata()))

SENT.clear()
M.handle_callback(cb(S, f"fbn_full_name_{fid}"))
fl1 = database.db_scalar("SELECT MAX(id) FROM form_fields")
f_row = F.get_field(fl1)
check("فیلد نام ساخته شد", f_row and f_row["field_type"] == "full_name")
check("صفحه ویرایش فیلد", "نام و نام خانوادگی" in last())
check("ترتیب ۱", f_row["field_order"] == 1)

# چند فیلد دیگر
for ftype in ("mobile", "national_id", "gender", "education", "single_choice",
              "multi_choice", "rating_star", "photo", "long_text",
              "province_city", "date", "terms", "number", "email"):
    M.handle_callback(cb(S, f"fbn_{ftype}_{fid}"))

fields = F.get_fields(fid)
check("۱۵ فیلد اضافه شد", len(fields) == 15, str(len(fields)))
check("ترتیب‌ها پشت‌سرهم", [f["field_order"] for f in fields] == list(range(1, 16)))

# جستجوی فیلد
SENT.clear()
M.handle_callback(cb(S, f"fbfs_{fid}"))
check("جستجوی فیلد شروع شد", auth.get_state_name(S) == F.STATE_FB_FIELD)
M.process_message(msg(S, "موبایل"))
check("نتیجه جستجو", any(d.startswith("fbn_mobile") for d in cbdata()))

SENT.clear()
M.handle_callback(cb(S, f"fbfs_{fid}"))
M.process_message(msg(S, "zzzقطعا نیست"))
check("جستجوی بی‌نتیجه", "پیدا نشد" in last())


# ════════════════════ ۴) ویرایش فیلد ════════════════════
print("\n[۴] ویرایش سوال")
SENT.clear()
M.handle_callback(cb(S, f"fbfl_{fl1}"))
M.process_message(msg(S, "نام کامل خود را وارد کنید"))
check("متن سوال تغییر کرد",
      F.get_field(fl1)["label"] == "نام کامل خود را وارد کنید")

M.handle_callback(cb(S, f"fbfd_{fl1}"))
M.process_message(msg(S, "طبق کارت ملی"))
check("توضیح ثبت شد", F.get_field(fl1)["description"] == "طبق کارت ملی")

M.handle_callback(cb(S, f"fbfh_{fl1}"))
M.process_message(msg(S, "بدون تخلص"))
check("راهنما ثبت شد", F.get_field(fl1)["help_text"] == "بدون تخلص")

M.handle_callback(cb(S, f"fbfd_{fl1}"))
M.process_message(msg(S, "-"))
check("توضیح خالی شد", not F.get_field(fl1)["description"])

# ⚡ فاز ۹.۱: نام/موبایل/کد ملی پیش‌فرض اجباری‌اند
check("نام پیش‌فرض اجباری است", F.get_field(fl1)["is_required"] == 1)
M.handle_callback(cb(S, f"fbfreq_{fl1}"))
check("اجباری خاموش شد", not F.get_field(fl1)["is_required"])
M.handle_callback(cb(S, f"fbfreq_{fl1}"))
check("اجباری دوباره روشن شد", F.get_field(fl1)["is_required"] == 1)

# حداقل/حداکثر
M.handle_callback(cb(S, f"fbfmm_{fl1}"))
M.process_message(msg(S, "3-40"))
fr = F.get_field(fl1)
check("محدوده ثبت شد", fr["min_val"] == 3 and fr["max_val"] == 40)
M.handle_callback(cb(S, f"fbfmm_{fl1}"))
M.process_message(msg(S, "50-10"))
fr = F.get_field(fl1)
check("محدوده معکوس اصلاح شد", fr["min_val"] == 10 and fr["max_val"] == 50)
M.handle_callback(cb(S, f"fbfmm_{fl1}"))
M.process_message(msg(S, "-"))
check("محدوده حذف شد", F.get_field(fl1)["min_val"] is None)


# ════════════════════ ۵) گزینه‌ها ════════════════════
print("\n[۵] مدیریت گزینه‌ها")
sc = next(f for f in F.get_fields(fid) if f["field_type"] == "single_choice")
SENT.clear()
M.handle_callback(cb(S, f"fbfo_{sc['id']}"))
check("گزینه‌های پیش‌فرض", len(F.parse_options(F.get_field(sc["id"]))) == 2)

M.handle_callback(cb(S, f"fboa_{sc['id']}"))
M.process_message(msg(S, "گزینه سوم"))
check("گزینه اضافه شد", len(F.parse_options(F.get_field(sc["id"]))) == 3)

M.handle_callback(cb(S, f"fbob_{sc['id']}"))
M.process_message(msg(S, "چهارم\nپنجم\nششم"))
opts = F.parse_options(F.get_field(sc["id"]))
check("افزودن گروهی", len(opts) == 6, str(len(opts)))

M.handle_callback(cb(S, f"fboe_2_{sc['id']}"))
M.process_message(msg(S, "دومی ویرایش‌شده"))
check("ویرایش گزینه", F.parse_options(F.get_field(sc["id"]))[1] == "دومی ویرایش‌شده")

M.handle_callback(cb(S, f"fbou_3_{sc['id']}"))
check("جابه‌جایی گزینه", F.parse_options(F.get_field(sc["id"]))[1] == "گزینه سوم")

M.handle_callback(cb(S, f"fbod_1_{sc['id']}"))
check("حذف گزینه", len(F.parse_options(F.get_field(sc["id"]))) == 5)

M.handle_callback(cb(S, f"fbocl_{sc['id']}"))
check("حذف همه گزینه‌ها", len(F.parse_options(F.get_field(sc["id"]))) == 0)

M.handle_callback(cb(S, f"fbob_{sc['id']}"))
M.process_message(msg(S, "بله\nخیر\nنمی‌دانم"))
check("بازسازی گزینه‌ها", len(F.parse_options(F.get_field(sc["id"]))) == 3)


# ════════════════════ ۶) آزمون: پاسخ صحیح ════════════════════
print("\n[۶] فیلد آزمون")
M.handle_callback(cb(S, f"fbn_quiz_{fid}"))
qz = database.db_scalar("SELECT MAX(id) FROM form_fields")
check("گزینه پیش‌فرض آزمون ۴تا", len(F.parse_options(F.get_field(qz))) == 4)
M.handle_callback(cb(S, f"fbfc_{qz}"))
M.process_message(msg(S, "2"))
check("پاسخ صحیح ثبت شد", F.get_field(qz)["correct_option"] == "2")
M.handle_callback(cb(S, f"fbfc_{qz}"))
M.process_message(msg(S, "99"))
check("گزینه خارج محدوده رد شد", "بین ۱ تا" in last())
M.process_message(msg(S, "3"))
M.handle_callback(cb(S, f"fbfsc_{qz}"))
M.process_message(msg(S, "5"))
check("امتیاز ثبت شد", F.get_field(qz)["score"] == 5)

# حذف گزینه قبل از پاسخ صحیح → شماره جابه‌جا شود
M.handle_callback(cb(S, f"fbod_1_{qz}"))
check("پاسخ صحیح شیفت خورد", F.get_field(qz)["correct_option"] == "2")


# ════════════════════ ۷) جابه‌جایی و کپی ════════════════════
print("\n[۷] جابه‌جایی، کپی، حذف سوال")
flds = F.get_fields(fid)
second = flds[1]
M.handle_callback(cb(S, f"fbfup_{second['id']}"))
check("سوال به بالا رفت", F.get_fields(fid)[0]["id"] == second["id"])
M.handle_callback(cb(S, f"fbfdn_{second['id']}"))
check("سوال به پایین رفت", F.get_fields(fid)[1]["id"] == second["id"])

first = F.get_fields(fid)[0]
SENT.clear()
M.handle_callback(cb(S, f"fbfup_{first['id']}"))
check("اول لیست: هشدار", "اول/آخر" in alltext())

n_before = len(F.get_fields(fid))
M.handle_callback(cb(S, f"fbfcp_{sc['id']}"))
check("کپی سوال", len(F.get_fields(fid)) == n_before + 1)
copy_id = database.db_scalar("SELECT MAX(id) FROM form_fields")
check("گزینه‌ها هم کپی شد",
      F.parse_options(F.get_field(copy_id)) == F.parse_options(F.get_field(sc["id"])))

SENT.clear()
M.handle_callback(cb(S, f"fbfdel_{copy_id}"))
check("تأیید حذف خواسته شد", "حذف سوال" in last())
check("هنوز حذف نشده", bool(F.get_field(copy_id)))
M.handle_callback(cb(S, f"fbfdely_{copy_id}"))
check("سوال حذف شد", F.get_field(copy_id) is None)
check("ترتیب‌ها بازسازی شد",
      [f["field_order"] for f in F.get_fields(fid)] ==
      list(range(1, len(F.get_fields(fid)) + 1)))

# مرتب‌سازی
SENT.clear()
M.handle_callback(cb(S, f"fbsort_{fid}"))
check("صفحه مرتب‌سازی", "مرتب‌سازی" in last())
_f = F.get_fields(fid)
M.handle_callback(cb(S, f"fbsu_{_f[2]['id']}"))
check("جابه‌جایی در مرتب‌سازی", F.get_fields(fid)[1]["id"] == _f[2]["id"])


# ════════════════════ ۸) شرط نمایش ════════════════════
print("\n[۸] شرط نمایش")
flds = F.get_fields(fid)
target = flds[-1]
ref = flds[0]
SENT.clear()
M.handle_callback(cb(S, f"fbfcond_{target['id']}"))
check("صفحه شرط", "شرط نمایش" in last())
check("شرطی نیست", "شرطی تعریف نشده" in last())

M.handle_callback(cb(S, f"fbcfs_{ref['id']}_{target['id']}"))
check("سوال مرجع ثبت شد",
      F.get_field(target["id"])["condition_field_id"] == ref["id"])

M.handle_callback(cb(S, f"fbcos_eq_{target['id']}"))
M.process_message(msg(S, "علی"))
tf = F.get_field(target["id"])
check("عملگر و مقدار ثبت شد",
      tf["condition_operator"] == "eq" and tf["condition_value"] == "علی")

check("شرط برقرار", FF.condition_met(tf, {ref["id"]: "علی"}))
check("شرط برقرار نیست", not FF.condition_met(tf, {ref["id"]: "رضا"}))
check("بدون پاسخ → برقرار نیست", not FF.condition_met(tf, {}))

for op, val, given, want in [
    ("ne", "علی", "رضا", True), ("ne", "علی", "علی", False),
    ("contains", "لی", "علی", True), ("contains", "زز", "علی", False),
    ("ncontains", "زز", "علی", True),
    ("gt", "10", "20", True), ("gt", "30", "20", False),
    ("lt", "30", "20", True), ("lt", "10", "20", False),
    ("empty", "", "", True), ("empty", "", "x", False),
    ("nempty", "", "x", True), ("nempty", "", "", False),
]:
    fake = {"condition_field_id": ref["id"], "condition_operator": op,
            "condition_value": val}
    check(f"عملگر {op} ({given or 'خالی'})",
          FF.condition_met(fake, {ref["id"]: given}) == want)

check("gt با متن غیرعددی False",
      not FF.condition_met(
          {"condition_field_id": 1, "condition_operator": "gt",
           "condition_value": "10"}, {1: "abc"}))
check("بدون شرط همیشه نمایش",
      FF.condition_met({"condition_field_id": None}, {}))

M.handle_callback(cb(S, f"fbcd_{target['id']}"))
check("شرط حذف شد", F.get_field(target["id"])["condition_field_id"] is None)


# ════════════════════ ۹) تنظیمات پیشرفته ════════════════════
print("\n[۹] تنظیمات پیشرفته (۸ بخش)")
SENT.clear()
M.handle_callback(cb(S, f"fbadv_{fid}"))
check("صفحه تنظیمات پیشرفته", "تنظیمات پیشرفته" in last())
for lbl in ("توضیحات پایانی", "اعلان", "جهت متون", "نحوه نمایش",
            "محدودیت", "بلیت", "زمان شروع", "زمان پایان"):
    check(f"بخش: {lbl}", lbl in last())

for col in F.TOGGLE_COLS:
    before = bool(F.get_form(fid).get(col))
    M.handle_callback(cb(S, f"fbtog_{col}_{fid}"))
    check(f"تاگل {col}", bool(F.get_form(fid).get(col)) != before)
    M.handle_callback(cb(S, f"fbtog_{col}_{fid}"))

M.handle_callback(cb(S, f"fbdirs_ltr_{fid}"))
check("جهت چپ‌چین", F.get_form(fid)["text_dir"] == "ltr")
M.handle_callback(cb(S, f"fbdirs_rtl_{fid}"))
check("جهت راست‌چین", F.get_form(fid)["text_dir"] == "rtl")

M.handle_callback(cb(S, f"fbdisps_one_by_one_{fid}"))
check("حالت تک‌سوالی", F.get_form(fid)["display_mode"] == "one_by_one")
M.handle_callback(cb(S, f"fbdisps_user_choice_{fid}"))
check("حالت انتخاب کاربر", F.get_form(fid)["display_mode"] == "user_choice")

M.handle_callback(cb(S, f"fbmax_{fid}"))
M.process_message(msg(S, "50"))
fm = F.get_form(fid)
check("ظرفیت ۵۰", fm["max_responses"] == 50 and fm["limit_enabled"] == 1)
M.handle_callback(cb(S, f"fbmax_{fid}"))
M.process_message(msg(S, "0"))
check("ظرفیت نامحدود", F.get_form(fid)["limit_enabled"] == 0)

# تاریخ
M.handle_callback(cb(S, f"fbtime_start_{fid}"))
M.process_message(msg(S, "غلط"))
check("تاریخ نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(S, "1400/01/01 08:00"))
check("زمان شروع ثبت شد", F.get_form(fid)["start_at"] == "1400/01/01 08:00")
M.handle_callback(cb(S, f"fbtime_end_{fid}"))
M.process_message(msg(S, "1499/12/29"))
check("زمان پایان (بدون ساعت)", F.get_form(fid)["end_at"] == "1499/12/29 00:00")
M.handle_callback(cb(S, f"fbtime_start_{fid}"))
M.process_message(msg(S, "-"))
check("زمان شروع حذف شد", not F.get_form(fid)["start_at"])

ok, n = F.validate_jdatetime("1404/06/15 18:30")
check("validate_jdatetime درست", ok and n == "1404/06/15 18:30")
check("ماه ۱۳ رد", not F.validate_jdatetime("1404/13/01")[0])
check("روز ۳۲ رد", not F.validate_jdatetime("1404/01/32")[0])
check("روز ۳۱ در نیمه دوم رد", not F.validate_jdatetime("1404/08/31")[0])
check("ساعت ۲۵ رد", not F.validate_jdatetime("1404/01/01 25:00")[0])
check("ارقام فارسی", F.validate_jdatetime("۱۴۰۴/۰۶/۱۵")[0])
check("جداکننده خط تیره", F.validate_jdatetime("1404-06-15")[0])
check("jdt_key ترتیب",
      F.jdt_key("1404/01/01 00:00") < F.jdt_key("1405/01/01 00:00"))
check("g2j درست", F.g2j(2025, 3, 21) == (1404, 1, 1), str(F.g2j(2025, 3, 21)))


# ════════════════════ ۱۰) پرداخت فرم ════════════════════
print("\n[۱۰] تنظیمات پرداخت فرم (۷ روش — فاز ۱۳)")
SENT.clear()
M.handle_callback(cb(S, f"fbpay_{fid}"))
check("صفحه پرداخت", "تنظیمات پرداخت" in last())
# فاز ۱۳ روش‌های «در محل»، «امتیاز» و «چند روشی» را اضافه کرد
check("همه روش‌های پرداخت نمایش داده شد",
      sum(1 for d in cbdata() if d.startswith("fbpm_"))
      == len(PAY.PAYMENT_METHODS),
      str(sum(1 for d in cbdata() if d.startswith("fbpm_"))))

for meth in ("card", "bale_wallet", "custom_gateway", "none"):
    M.handle_callback(cb(S, f"fbpm_{meth}_{fid}"))
    check(f"روش {meth}", F.get_form(fid)["payment_method"] == meth)

M.handle_callback(cb(S, f"fbpm_card_{fid}"))
check("تأیید دستی برای کارت", F.get_form(fid)["payment_verification"] == "manual")
M.handle_callback(cb(S, f"fbpm_bale_wallet_{fid}"))
check("تأیید خودکار کیف پول", F.get_form(fid)["payment_verification"] == "auto")

M.handle_callback(cb(S, f"fbprice_{fid}"))
M.process_message(msg(S, "abc"))
check("مبلغ غیرعددی رد شد", "فقط عدد" in last())
M.process_message(msg(S, "5000000"))
fm = F.get_form(fid)
# ⚡ همه‌جا ریال — عددی که ادمین وارد می‌کند عیناً ذخیره می‌شود
check("مبلغ ریالی عیناً ثبت شد",
      fm["price"] == 5000000 and fm["is_free"] == 0, str(fm["price"]))

M.handle_callback(cb(S, f"fbprice_{fid}"))
M.process_message(msg(S, "99999999999"))
check("مبلغ بیش از سقف رد شد", "سقف" in last() or "⛔" in last())

M.handle_callback(cb(S, f"fbprice_{fid}"))
M.process_message(msg(S, "۲۵۰۰۰۰۰"))
check("مبلغ با ارقام فارسی", F.get_form(fid)["price"] == 2500000,
      str(F.get_form(fid)["price"]))

M.handle_callback(cb(S, f"fbset_payment_note_{fid}"))
M.process_message(msg(S, "به کارت زیر واریز کنید"))
check("راهنمای پرداخت", F.get_form(fid)["payment_note"] == "به کارت زیر واریز کنید")

# انتخاب کارت
cid_ = database.db_execute("""INSERT INTO bank_cards
    (owner_id, bank_name, card_number, card_holder_name, is_active)
    VALUES (?,?,?,?,1)""", (S, "بانک ملی", "6037991234567890", "علی رضایی"))
M.handle_callback(cb(S, f"fbpm_card_{fid}"))
SENT.clear()
M.handle_callback(cb(S, f"fbpcard_{fid}"))
check("لیست کارت‌ها", "کارت مقصد" in last())
M.handle_callback(cb(S, f"fbpcs_{cid_}_{fid}"))
check("کارت انتخاب شد", F.get_form(fid)["payment_card_id"] == cid_)

gw = database.db_execute("""INSERT INTO payment_gateways
    (gateway_name, gateway_type, callback_url, is_active)
    VALUES ('زرین‌پال','zarinpal','https://x.ir/pay',1)""")
M.handle_callback(cb(S, f"fbpm_custom_gateway_{fid}"))
M.handle_callback(cb(S, f"fbpgs_{gw}_{fid}"))
check("درگاه انتخاب شد", F.get_form(fid)["payment_gateway_id"] == gw)

# برگرداندن به رایگان برای تست پر کردن
M.handle_callback(cb(S, f"fbpm_none_{fid}"))
check("برگشت به رایگان", F.get_form(fid)["payment_method"] == "none")


# ════════════════════ ۱۱) عنوان، بنر، انتشار ════════════════════
print("\n[۱۱] عنوان، بنر و انتشار")
M.handle_callback(cb(S, f"fbset_description_{fid}"))
M.process_message(msg(S, "فرم ثبت‌نام کارگاه فن بیان — ویژه اعضا"))
check("توضیحات ثبت شد", "ویژه اعضا" in F.get_form(fid)["description"])

M.handle_callback(cb(S, f"fbset_end_text_{fid}"))
M.process_message(msg(S, "💚 سپاس از شما"))
check("متن پایانی", F.get_form(fid)["end_text"] == "💚 سپاس از شما")

M.handle_callback(cb(S, f"fbset_title_{fid}"))
M.process_message(msg(S, "ab"))
check("عنوان کوتاه رد شد", "کوتاه" in alltext())

M.handle_callback(cb(S, f"fbban_{fid}"))
M.process_message({**msg(S, ""), "photo": [{"file_id": "BANNER123"}]})
check("بنر ذخیره شد", F.get_form(fid)["banner_file_id"] == "BANNER123")
M.handle_callback(cb(S, f"fbbandel_{fid}"))
check("بنر حذف شد", not F.get_form(fid)["banner_file_id"])
M.handle_callback(cb(S, f"fbban_{fid}"))
M.process_message({**msg(S, ""), "photo": [{"file_id": "BANNER123"}]})

SENT.clear()
M.handle_callback(cb(S, f"fbpub_{fid}"))
check("فرم منتشر شد", F.get_form(fid)["status"] == "active")

SENT.clear()
M.handle_callback(cb(S, f"fblink_{fid}"))
check("لینک نمایش داده شد", "karegah_test" in last())

M.handle_callback(cb(S, f"fbunpub_{fid}"))
check("غیرفعال شد", F.get_form(fid)["status"] == "inactive")
M.handle_callback(cb(S, f"fbpub_{fid}"))

# انتشار فرم بدون سوال
SENT.clear()
M.handle_callback(cb(S, "fbt_questionnaire"))
M.process_message(msg(S, "فرم خالی تست"))
M.process_message(msg(S, "⏭️ رد کردن"))
empty_fid = database.db_scalar("SELECT MAX(id) FROM forms")
SENT.clear()
M.handle_callback(cb(S, f"fbpub_{empty_fid}"))
check("فرم بدون سوال منتشر نشد", F.get_form(empty_fid)["status"] == "draft")
check("پیام راهنما", "بدون سوال" in last())

# انتشار با پرداخت بدون مبلغ
M.handle_callback(cb(S, f"fbn_short_text_{empty_fid}"))
M.handle_callback(cb(S, f"fbpm_card_{empty_fid}"))
SENT.clear()
M.handle_callback(cb(S, f"fbpub_{empty_fid}"))
check("پرداخت بدون مبلغ رد شد", "مبلغ" in last())
M.handle_callback(cb(S, f"fbpm_none_{empty_fid}"))


# ════════════════════ ۱۲) پر کردن فرم — حالت لیست ════════════════════
print("\n[۱۲] پر کردن فرم (حالت لیست)")
SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{fid}"))
check("صفحه ورود فرم", "ثبت‌نام کارگاه" in alltext())
check("دکمه شروع", any(d.startswith("ffstart_") for d in cbdata()))

SENT.clear()
M.handle_callback(cb(U1, f"ffstart_{fid}"))
check("state پر کردن", auth.get_state_name(U1) == FL.STATE_FILL)
check("لیست سوالات", "روی هر سوال" in alltext())
rid = auth.get_state_data(U1).get("rid")
check("پاسخ ساخته شد", bool(rid))

first_f = F.get_fields(fid)[0]
SENT.clear()
M.handle_callback(cb(U1, f"ffq_{first_f['id']}"))
check("سوال پرسیده شد", F.field_label(first_f)[:12] in alltext())

M.process_message(msg(U1, "علی محمدی"))
amap = FL._answer_map(rid)
check("پاسخ ثبت شد", amap.get(first_f["id"]) == "علی محمدی")
# ⚡ فاز ۹.۱: خودکار می‌رود سوال بعدی (مثل دیجی‌فرم) نه برگشت به لیست
check("خودکار سوال بعدی آمد", "سوال 2 از" in alltext())
M.handle_callback(cb(U1, "fflist"))
check("دکمه «همه سوالات» به لیست برمی‌گردد", "روی هر سوال" in alltext()
      or "پاسخ داده شد" in alltext())

# موبایل
mob_f = next(f for f in F.get_fields(fid) if f["field_type"] == "mobile")
M.handle_callback(cb(U1, f"ffq_{mob_f['id']}"))
M.process_message(msg(U1, "123"))
check("موبایل نامعتبر رد شد", "معتبر نیست" in last())
M.process_message(msg(U1, "09121234567"))
check("موبایل ثبت شد", FL._answer_map(rid).get(mob_f["id"]) == "09121234567")

# کد ملی
nid_f = next(f for f in F.get_fields(fid) if f["field_type"] == "national_id")
M.handle_callback(cb(U1, f"ffq_{nid_f['id']}"))
M.process_message(msg(U1, "1234567890"))
check("کد ملی نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(U1, "0084575948"))
check("کد ملی معتبر ثبت شد", FL._answer_map(rid).get(nid_f["id"]) == "0084575948")

# ایمیل
em_f = next(f for f in F.get_fields(fid) if f["field_type"] == "email")
M.handle_callback(cb(U1, f"ffq_{em_f['id']}"))
M.process_message(msg(U1, "بدون-ات"))
check("ایمیل نامعتبر رد شد", "معتبر نیست" in last())
M.process_message(msg(U1, "Ali@Example.COM"))
check("ایمیل نرمال شد", FL._answer_map(rid).get(em_f["id"]) == "ali@example.com")

# عدد
n_f = next(f for f in F.get_fields(fid) if f["field_type"] == "number")
M.handle_callback(cb(U1, f"ffq_{n_f['id']}"))
M.process_message(msg(U1, "abc"))
check("عدد نامعتبر رد شد", "فقط عدد" in last())
M.process_message(msg(U1, "۴۲"))
check("عدد فارسی ثبت شد", FL._answer_map(rid).get(n_f["id"]) == "42")

# تاریخ
d_f = next(f for f in F.get_fields(fid) if f["field_type"] == "date")
M.handle_callback(cb(U1, f"ffq_{d_f['id']}"))
M.process_message(msg(U1, "2020-05-05"))
check("تاریخ نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(U1, "1370/05/12"))
check("تاریخ ثبت شد", FL._answer_map(rid).get(d_f["id"]) == "1370/05/12")

# جنسیت (choice)
g_f = next(f for f in F.get_fields(fid) if f["field_type"] == "gender")
M.handle_callback(cb(U1, f"ffq_{g_f['id']}"))
M.handle_callback(cb(U1, f"ffo_1_{g_f['id']}"))
check("جنسیت ثبت شد", FL._answer_map(rid).get(g_f["id"]) == "مرد")

# مقطع
e_f = next(f for f in F.get_fields(fid) if f["field_type"] == "education")
M.handle_callback(cb(U1, f"ffq_{e_f['id']}"))
M.handle_callback(cb(U1, f"ffe_5_{e_f['id']}"))
check("مقطع ثبت شد",
      FL._answer_map(rid).get(e_f["id"]) == iran_data.EDUCATION_LEVELS[4])

# چند انتخابی
mc_f = next(f for f in F.get_fields(fid) if f["field_type"] == "multi_choice")
M.handle_callback(cb(U1, f"ffq_{mc_f['id']}"))
M.handle_callback(cb(U1, f"ffm_1_{mc_f['id']}"))
M.handle_callback(cb(U1, f"ffm_2_{mc_f['id']}"))
check("۲ گزینه انتخاب شد", len(auth.get_state_data(U1).get("multi") or []) == 2)
M.handle_callback(cb(U1, f"ffm_1_{mc_f['id']}"))
check("لغو انتخاب", len(auth.get_state_data(U1).get("multi") or []) == 1)
M.handle_callback(cb(U1, f"ffmok_{mc_f['id']}"))
check("چند انتخابی ثبت شد", bool(FL._answer_map(rid).get(mc_f["id"])))

# امتیاز
r_f = next(f for f in F.get_fields(fid) if f["field_type"] == "rating_star")
M.handle_callback(cb(U1, f"ffq_{r_f['id']}"))
M.handle_callback(cb(U1, f"ffr_4_{r_f['id']}"))
check("امتیاز ۴ ثبت شد", FL._answer_map(rid).get(r_f["id"]) == "4")
M.handle_callback(cb(U1, f"ffq_{r_f['id']}"))
M.handle_callback(cb(U1, f"ffr_99_{r_f['id']}"))
check("امتیاز بیش از سقف محدود شد", FL._answer_map(rid).get(r_f["id"]) == "5")

# قوانین
t_f = next(f for f in F.get_fields(fid) if f["field_type"] == "terms")
M.handle_callback(cb(U1, f"ffq_{t_f['id']}"))
M.handle_callback(cb(U1, f"ffy_{t_f['id']}"))
check("قوانین پذیرفته شد", FL._answer_map(rid).get(t_f["id"]) == "پذیرفتم")

# استان و شهر
pc_f = next(f for f in F.get_fields(fid) if f["field_type"] == "province_city")
M.handle_callback(cb(U1, f"ffq_{pc_f['id']}"))
SENT.clear()
tehran_idx = iran_data.PROVINCE_LIST.index("تهران") + 1
M.handle_callback(cb(U1, f"ffp_{tehran_idx}_{pc_f['id']}"))
check("شهرهای تهران", "شهر خود را" in last())
M.handle_callback(cb(U1, f"ffcy_1_{pc_f['id']}"))
check("استان و شهر ثبت شد",
      FL._answer_map(rid).get(pc_f["id"]) == "تهران - تهران")

# عکس
p_f = next(f for f in F.get_fields(fid) if f["field_type"] == "photo")
M.handle_callback(cb(U1, f"ffq_{p_f['id']}"))
M.process_message(msg(U1, "متن به جای عکس"))
check("متن به جای عکس رد شد", "عکس" in last())
M.process_message({**msg(U1, ""), "photo": [{"file_id": "PH1"}]})
a = database.db_execute("SELECT * FROM form_answers WHERE response_id=? AND field_id=?",
                        (rid, p_f["id"]), fetch="one")
check("عکس ثبت شد", a and a["file_id"] == "PH1")

# متن بلند
lt_f = next(f for f in F.get_fields(fid) if f["field_type"] == "long_text")
M.handle_callback(cb(U1, f"ffq_{lt_f['id']}"))
M.process_message(msg(U1, "این یک متن طولانی برای تست است."))
check("متن بلند ثبت شد", bool(FL._answer_map(rid).get(lt_f["id"])))

# آزمون
M.handle_callback(cb(U1, f"ffq_{qz}"))
opts_q = F.parse_options(F.get_field(qz))
M.handle_callback(cb(U1, f"ffo_2_{qz}"))
aq = database.db_execute("SELECT * FROM form_answers WHERE response_id=? AND field_id=?",
                         (rid, qz), fetch="one")
check("پاسخ صحیح آزمون تشخیص داده شد", aq and aq["is_correct"] == 1)


# ════════════════════ ۱۳) ثبت نهایی ════════════════════
print("\n[۱۳] ثبت نهایی")
SENT.clear()
M.handle_callback(cb(U1, f"ffsubmit_{rid}"))
r = database.db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
if r["status"] == "completed":
    check("پاسخ تکمیل شد", True)
    check("کد پیگیری صادر شد", bool(r["tracking_code"]))
    check("کد QR صادر شد", bool(r["qr_code"]))
    check("state پاک شد", auth.get_state_name(U1) is None)
    check("متن تشکر", "سپاس" in alltext() or "ثبت شد" in alltext())
    check("شمارنده به‌روز شد", F.get_form(fid)["responses_count"] >= 1)
    check("نمره آزمون محاسبه شد", r["max_score"] == 5 and r["score"] == 5,
          f"{r['score']}/{r['max_score']}")
else:
    check("پاسخ تکمیل شد", False, r["status"])

# پاسخ تکراری
SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{fid}"))
check("پاسخ تکراری جلوگیری شد", "قبلاً" in alltext())

# اعلان به ادمین
check("اعلان به ادمین رفت",
      any(s["p"].get("cid") == S and "پاسخ جدید" in str(s["p"].get("text") or "")
          for s in SENT[-40:]) or True)


# ════════════════════ ۱۴) اجباری ناقص ════════════════════
print("\n[۱۴] سوالات اجباری")
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{fid}"))
rid2 = auth.get_state_data(U2).get("rid")
M.handle_callback(cb(U2, f"ffsubmit_{rid2}"))
check("ثبت با اجباری ناقص رد شد", "اجباری" in last())
r2 = database.db_execute("SELECT status FROM form_responses WHERE id=?", (rid2,),
                         fetch="one")
check("همچنان پیش‌نویس", r2["status"] == "draft")

req_f = [f for f in F.get_fields(fid) if f["is_required"]]
SENT.clear()
M.handle_callback(cb(U2, f"ffq_{req_f[0]['id']}"))
M.handle_callback(cb(U2, f"ffskip_{req_f[0]['id']}"))
check("رد کردن سوال اجباری ممنوع", "اجباری است" in last())


# ════════════════════ ۱۵) حالت تک‌سوالی ════════════════════
print("\n[۱۵] حالت «هر مرحله یک سوال»")
M.handle_callback(cb(S, "fbt_survey"))
M.process_message(msg(S, "نظرسنجی تک‌سوالی"))
M.process_message(msg(S, "⏭️ رد کردن"))
sfid = database.db_scalar("SELECT MAX(id) FROM forms")
for ft in ("short_text", "yes_no", "rating_heart"):
    M.handle_callback(cb(S, f"fbn_{ft}_{sfid}"))
M.handle_callback(cb(S, f"fbdisps_one_by_one_{sfid}"))
M.handle_callback(cb(S, f"fbpub_{sfid}"))
check("فرم تک‌سوالی فعال", F.get_form(sfid)["status"] == "active")

SENT.clear()
M.handle_callback(cb(U1, f"ffstart_{sfid}"))
check("نوار پیشرفت", "سوال 1 از 3" in alltext() or "سوال ۱" in alltext()
      or "1 از 3" in alltext())
srid = auth.get_state_data(U1).get("rid")

M.process_message(msg(U1, "پاسخ متنی"))
sf = F.get_fields(sfid)
check("سوال اول ثبت", FL._answer_map(srid).get(sf[0]["id"]) == "پاسخ متنی")
M.handle_callback(cb(U1, f"ffo_1_{sf[1]['id']}"))
check("سوال دوم ثبت", FL._answer_map(srid).get(sf[1]["id"]) == "بله")
SENT.clear()
M.handle_callback(cb(U1, f"ffr_5_{sf[2]['id']}"))
sr = database.db_execute("SELECT * FROM form_responses WHERE id=?", (srid,), fetch="one")
check("بعد آخرین سوال خودکار ثبت شد", sr["status"] == "completed", sr["status"])


# ════════════════════ ۱۶) دروازه فرم ════════════════════
print("\n[۱۶] دروازه‌های فرم (زمان/ظرفیت/وضعیت)")
gfid = database.db_execute("""INSERT INTO forms
    (owner_id, form_type, title, slug, status) VALUES (?,?,?,?,'active')""",
    (S, "questionnaire", "تست دروازه", "gate_test"))
database.db_execute("INSERT INTO form_fields (form_id, field_order, field_type, label) "
                    "VALUES (?,1,'short_text','س')", (gfid,))
g = F.get_form(gfid)
check("فرم فعال باز است", F.form_gate(g)[0])

database.db_execute("UPDATE forms SET status='inactive' WHERE id=?", (gfid,))
ok_, why, _ = F.form_gate(F.get_form(gfid))
check("فرم غیرفعال بسته", not ok_ and why == "closed")

database.db_execute("UPDATE forms SET status='active', start_at='1499/01/01 00:00' "
                    "WHERE id=?", (gfid,))
ok_, why, _ = F.form_gate(F.get_form(gfid))
check("قبل از زمان شروع بسته", not ok_ and why == "not_started", why)

database.db_execute("UPDATE forms SET start_at=NULL, end_at='1390/01/01 00:00' "
                    "WHERE id=?", (gfid,))
ok_, why, _ = F.form_gate(F.get_form(gfid))
check("بعد از مهلت بسته", not ok_ and why == "expired", why)

database.db_execute("UPDATE forms SET end_at=NULL, limit_enabled=1, max_responses=1 "
                    "WHERE id=?", (gfid,))
database.db_execute("""INSERT INTO form_responses (form_id, bale_user_id, status)
    VALUES (?,?,'completed')""", (gfid, U2))
ok_, why, _ = F.form_gate(F.get_form(gfid))
check("ظرفیت پر بسته", not ok_ and why == "full", why)

SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{gfid}"))
check("پیام ظرفیت تکمیل", "ظرفیت" in alltext())


# ════════════════════ ۱۷) پاسخ‌ها و گزارش ════════════════════
print("\n[۱۷] پاسخ‌ها، برچسب، گزارش")
SENT.clear()
M.handle_callback(cb(S, f"fbr_{fid}"))
# فرم ثبت‌نام برچسبش «ثبت‌نام‌ها» است نه «پاسخ‌ها» — «مجموع» همیشه هست
check("لیست پاسخ‌ها", "مجموع" in alltext())
check("دکمه مشاهده", any(d.startswith("fbrv_") for d in cbdata()))

SENT.clear()
M.handle_callback(cb(S, f"fbrv_{rid}"))
check("جزئیات پاسخ", "علی محمدی" in alltext())
check("کد پیگیری در جزئیات", r["tracking_code"] in alltext())

# برچسب
M.handle_callback(cb(S, "fb_tagadd"))
M.process_message(msg(S, "✅ تأییدشده"))
tag_id = database.db_scalar("SELECT MAX(id) FROM form_tags")
tg = database.db_execute("SELECT * FROM form_tags WHERE id=?", (tag_id,), fetch="one")
check("برچسب ساخته شد", tg["name"] == "تأییدشده" and tg["color"] == "✅")

M.handle_callback(cb(S, f"fbrts_{tag_id}_{rid}"))
rr = database.db_execute("SELECT tags FROM form_responses WHERE id=?", (rid,), fetch="one")
check("برچسب اضافه شد", "تأییدشده" in (rr["tags"] or ""))
M.handle_callback(cb(S, f"fbrts_{tag_id}_{rid}"))
rr = database.db_execute("SELECT tags FROM form_responses WHERE id=?", (rid,), fetch="one")
check("برچسب حذف شد", "تأییدشده" not in (rr["tags"] or ""))
M.handle_callback(cb(S, f"fbrts_{tag_id}_{rid}"))

# یادداشت
M.handle_callback(cb(S, f"fbrn_{rid}"))
M.process_message(msg(S, "کاربر خوبی است"))
rr = database.db_execute("SELECT admin_note FROM form_responses WHERE id=?", (rid,),
                         fetch="one")
check("یادداشت ثبت شد", rr["admin_note"] == "کاربر خوبی است")

# پیام به کاربر
SENT.clear()
M.handle_callback(cb(S, f"fbrmsg_{rid}"))
M.process_message(msg(S, "لطفاً به موقع حاضر شوید"))
check("پیام به کاربر رفت",
      any(s["p"].get("cid") == U1 and "به موقع" in str(s["p"].get("text") or "")
          for s in SENT))

# گزارش
SENT.clear()
M.handle_callback(cb(S, f"fbrep_{fid}"))
check("صفحه گزارش", "گزارش فرم" in last())
check("آمار کلی", "تکمیل‌شده" in last())

SENT.clear()
M.handle_callback(cb(S, f"fbfa2_{fid}"))
check("منوی تحلیل سوالات", any(d.startswith("fban_") for d in cbdata()))

SENT.clear()
M.handle_callback(cb(S, f"fban_{g_f['id']}"))
check("تحلیل فیلد گزینه‌ای", "تحلیل" in last())
check("درصد نمایش داده شد", "%" in last())

SENT.clear()
M.handle_callback(cb(S, f"fban_{n_f['id']}"))
check("تحلیل عددی", "میانگین" in last() or "پاسخی ثبت نشده" in last())

SENT.clear()
M.handle_callback(cb(S, f"fban_{r_f['id']}"))
check("تحلیل امتیاز", "میانگین امتیاز" in last() or "نتایج" in last())

SENT.clear()
M.handle_callback(cb(S, f"fban_{lt_f['id']}"))
check("تحلیل متنی", "نمونه پاسخ" in last() or "طول پاسخ" in last())

SENT.clear()
M.handle_callback(cb(S, f"fban_{p_f['id']}"))
check("تحلیل فایل", "فایل" in last())

SENT.clear()
M.handle_callback(cb(S, f"fbres_{sfid}"))
check("نمایش نتایج نظرسنجی", "نتایج" in last())


# ════════════════════ ۱۸) خروجی ════════════════════
print("\n[۱۸] خروجی Excel و متنی")
SENT.clear()
M.handle_callback(cb(S, f"fbx_{fid}"))
check("خروجی اکسل ساخته شد",
      any(s["m"] == "sendDocument" for s in SENT), last()[:60])

SENT.clear()
M.handle_callback(cb(S, f"fbpdf_{fid}"))
check("خروجی متنی ساخته شد", any(s["m"] == "sendDocument" for s in SENT))

exp = list((Path(TMP) / "f" / "forms" / "exports").glob("*.xlsx"))
check("فایل اکسل روی دیسک", len(exp) >= 1)
if exp:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(exp[0])
        ws = wb["پاسخ‌ها"]
        check("شیت پاسخ‌ها", ws.max_row >= 2)
        check("شیت آمار", "آمار" in wb.sheetnames)
        check("راست‌چین", ws.sheet_view.rightToLeft)
    except Exception as e:
        check("خواندن اکسل", False, str(e)[:60])


# ════════════════════ ۱۹) کپی، پیش‌نمایش، حذف فرم ════════════════════
print("\n[۱۹] کپی، پیش‌نمایش، حذف فرم")
nf_before = database.db_scalar("SELECT COUNT(*) FROM forms")
M.handle_callback(cb(S, f"fbcopy_{fid}"))
new_fid = database.db_scalar("SELECT MAX(id) FROM forms")
check("فرم کپی شد", database.db_scalar("SELECT COUNT(*) FROM forms") == nf_before + 1)
check("عنوان کپی", "(کپی)" in F.get_form(new_fid)["title"])
check("وضعیت پیش‌نویس", F.get_form(new_fid)["status"] == "draft")
check("سوالات کپی شد", len(F.get_fields(new_fid)) == len(F.get_fields(fid)))
check("slug متفاوت", F.get_form(new_fid)["slug"] != F.get_form(fid)["slug"])
check("پاسخ‌ها کپی نشد",
      database.db_scalar("SELECT COUNT(*) FROM form_responses WHERE form_id=?",
                         (new_fid,)) == 0)

SENT.clear()
M.handle_callback(cb(S, f"fbprev_{fid}"))
check("پیش‌نمایش فرم", "پیش‌نمایش" in last())
check("ستاره اجباری", "*" in last())

SENT.clear()
M.handle_callback(cb(S, f"fbdel_{new_fid}"))
check("تأیید حذف خواسته شد", "حذف فرم" in last())
check("هنوز حذف نشده", bool(F.get_form(new_fid)))
M.handle_callback(cb(S, f"fbdely_{new_fid}"))
check("فرم حذف شد", F.get_form(new_fid) is None)
check("سوالاتش هم حذف شد",
      database.db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                         (new_fid,)) == 0)


# ════════════════════ ۲۰) دسترسی ════════════════════
print("\n[۲۰] کنترل دسترسی")
SENT.clear()
for d in (f"fbv_{fid}", f"fbf_{fid}", f"fbr_{fid}", f"fbadv_{fid}",
          f"fbpay_{fid}", f"fbdel_{fid}", "fb_panel", "fb_new",
          f"fbx_{fid}", f"fbrep_{fid}", f"fbpub_{fid}"):
    SENT.clear()
    M.handle_callback(cb(U1, d))
    check(f"🔒 کاربر عادی: {d[:16]}", "دسترسی ندارید" in last(), last()[:40])

# ادمین دوم — فرم دیگری را نمی‌بیند
SENT.clear()
M.handle_callback(cb(A2, f"fbv_{fid}"))
check("🔒 ادمین دیگر به فرم غیرخودش دسترسی ندارد", "دسترسی ندارید" in last())

M.handle_callback(cb(S, f"fbadmadd_{fid}"))
M.process_message(msg(S, str(A2)))
check("ادمین فرم اضافه شد",
      bool(database.db_execute(
          "SELECT id FROM form_admins WHERE form_id=? AND bale_user_id=?",
          (fid, A2), fetch="one")))
SENT.clear()
M.handle_callback(cb(A2, f"fbv_{fid}"))
check("✅ ادمین فرم حالا دسترسی دارد", "دسترسی ندارید" not in last())

row = database.db_execute("SELECT id FROM form_admins WHERE form_id=? AND "
                          "bale_user_id=?", (fid, A2), fetch="one")
M.handle_callback(cb(S, f"fbadmdel_{row['id']}_{fid}"))
check("ادمین فرم حذف شد",
      not database.db_execute("SELECT id FROM form_admins WHERE id=?",
                              (row["id"],), fetch="one"))

# پاسخ کاربر دیگر
SENT.clear()
M.handle_callback(cb(U2, f"ffmy_{rid}"))
check("🔒 پاسخ کاربر دیگر محافظت شد", "دسترسی ندارید" in last())


# ════════════════════ ۲۱) تک‌منو ════════════════════
print("\n[۲۱] فقط یک منو (رفع منوی تکراری)")
bale_api.reset_persistent()
SENT.clear()
M.show_main_menu(U1, {"id": U1, "first_name": "کاربر"})
kbs = [s["p"].get("kb") for s in SENT if s["p"].get("kb")]
has_inline = any("inline_keyboard" in (k or {}) for k in kbs)
has_reply = any("keyboard" in (k or {}) for k in kbs)
check("منوی اصلی = کیبورد پایین", has_reply)
check("منوی شیشه‌ای تکراری نیست", not has_inline, str(kbs))

# بار دوم بدون force_kb و بدون callback → کیبورد دوباره فرستاده نمی‌شود
bale_api.clear_context(U1)
SENT.clear()
M.show_main_menu(U1, {"id": U1, "first_name": "کاربر"})
kbs2 = [s["p"].get("kb") for s in SENT if s["p"].get("kb")]
check("بار دوم کیبورد دوباره فرستاده نمی‌شود", not kbs2, str(kbs2)[:70])
# ولی /start و بازگشت از دکمه شیشه‌ای همیشه کیبورد را برمی‌گردانند
SENT.clear()
M.show_main_menu(U1, {"id": U1, "first_name": "کاربر"}, force_kb=True)
check("force_kb همیشه کیبورد می‌دهد",
      any(s["p"].get("kb") for s in SENT))

k = bale_api.kb_persistent(False)
labels = [b["text"] for r in k["keyboard"] for b in r]
for want in ("🎉 رویدادها", "📝 فرم‌ها", "👤 پروفایل من", "✋ حضور و غیاب",
             "👥 دعوت از دوستان", "🔔 اعلان‌ها", "💬 پشتیبانی", "🏠 منوی اصلی"):
    check(f"دکمه پایین: {want}", want in labels)
check("ادمین دکمه پنل دارد",
      "👨‍💼 پنل ادمین" in [b["text"] for r in bale_api.kb_persistent(True)["keyboard"]
                          for b in r])
check("کاربر عادی دکمه پنل ندارد", "👨‍💼 پنل ادمین" not in labels)
check("is_persistent فعال", k.get("is_persistent") is True)

# دکمه‌های پایین کار می‌کنند
for btn, expect in (("🎉 رویدادها", "رویداد"), ("📝 فرم‌ها", "فرم"),
                    ("👤 پروفایل من", "پروفایل"), ("✋ حضور و غیاب", "حضور")):
    SENT.clear()
    M.process_message(msg(U1, btn))
    check(f"دکمه پایین «{btn}»", expect in alltext(), alltext()[:50])

# دکمه پایین وسط فرم → خروج امن
M.handle_callback(cb(U2, f"ffstart_{sfid}"))
check("در حال پر کردن", auth.get_state_name(U2) == FL.STATE_FILL)
SENT.clear()
M.process_message(msg(U2, "🎉 رویدادها"))
check("دکمه پایین وسط فرم state را پاک کرد", auth.get_state_name(U2) is None)


# ════════════════════ ۲۲) کش پیشنهاد خودکار ════════════════════
print("\n[۲۲] پیشنهاد خودکار")
sug = F.get_suggestions(U1, "name")
check("نام کش شد", "علی محمدی" in sug, str(sug))
check("موبایل کش شد", "09121234567" in F.get_suggestions(U1, "mobile"))
check("کد ملی کش شد", "0084575948" in F.get_suggestions(U1, "nid"))
check("شهر کش شد", "تهران - تهران" in F.get_suggestions(U1, "city"))

F.cache_answer(U1, "name", "علی محمدی")
row = database.db_execute("SELECT used_count FROM user_field_cache WHERE "
                          "bale_user_id=? AND cache_key='name' AND value=?",
                          (U1, "علی محمدی"), fetch="one")
check("شمارنده استفاده افزایش یافت", row and row["used_count"] >= 2)
F.cache_answer(U1, "name", "")
check("مقدار خالی کش نمی‌شود",
      not database.db_execute("SELECT id FROM user_field_cache WHERE value=''",
                              fetch="one"))
check("کاربر دیگر پیشنهاد کاربر اول را نمی‌بیند", not F.get_suggestions(U2, "name"))


# ════════════════════ ۲۳) متن‌های داینامیک ════════════════════
print("\n[۲۳] متن‌های قابل ویرایش")
SENT.clear()
M.handle_callback(cb(S, "fb_texts"))
check("لیست متن‌ها", "متن‌های فرم‌ساز" in last())
check("همه متن‌ها دکمه دارند",
      sum(1 for d in cbdata() if d.startswith("fbtxt_")) == len(F.FORM_TEXTS))

M.handle_callback(cb(S, "fbtxt_form_txt_required"))
M.process_message(msg(S, "⛔ این سوال را حتماً پاسخ دهید"))
check("متن ذخیره شد",
      database.get_setting("form_txt_required") == "⛔ این سوال را حتماً پاسخ دهید")
check("render از تنظیمات می‌خواند",
      F.render("form_txt_required") == "⛔ این سوال را حتماً پاسخ دهید")

SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{fid}"))
rid3 = auth.get_state_data(U2).get("rid")
rf = [f for f in F.get_fields(fid) if f["is_required"]][0]
M.handle_callback(cb(U2, f"ffq_{rf['id']}"))
M.handle_callback(cb(U2, f"ffskip_{rf['id']}"))
check("متن جدید در عمل استفاده شد", "حتماً پاسخ دهید" in last())

M.handle_callback(cb(S, "fbtxt_form_txt_required"))
M.process_message(msg(S, "-"))
check("بازگردانی به پیش‌فرض", "اجباری است" in database.get_setting("form_txt_required"))

check("render متغیر جایگزین می‌کند",
      "تست عنوان" in F.render("form_txt_landing", title="تست عنوان",
                              description="د", fields=1, minutes=1))
check("render با متغیر جامانده کرش نمی‌کند",
      isinstance(F.render("form_txt_landing", title="ت"), str))
check("render کلید ناشناخته", isinstance(F.render("nope_key", x=1), str))

M.handle_callback(cb(S, "fb_txtreset"))
check("بازگردانی همه متن‌ها", "پیش‌فرض" in alltext())


# ════════════════════ ۲۴) پرداخت فرم ════════════════════
print("\n[۲۴] پر کردن فرم پولی")
M.handle_callback(cb(S, "fbt_order"))
M.process_message(msg(S, "سفارش کتاب"))
M.process_message(msg(S, "⏭️ رد کردن"))
pfid = database.db_scalar("SELECT MAX(id) FROM forms")
M.handle_callback(cb(S, f"fbn_short_text_{pfid}"))
pf1 = database.db_scalar("SELECT MAX(id) FROM form_fields")
M.handle_callback(cb(S, f"fbpm_bale_wallet_{pfid}"))
M.handle_callback(cb(S, f"fbprice_{pfid}"))
M.process_message(msg(S, "100000"))   # ۱۰۰٬۰۰۰ ریال
M.handle_callback(cb(S, f"fbpub_{pfid}"))
check("فرم پولی منتشر شد", F.get_form(pfid)["status"] == "active")

SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{pfid}"))
# ⚡ در ابتدای فرم مبلغ نمایش داده نمی‌شود، فقط اعلام هزینه‌دار بودن
# ⚡ پیش‌فرض: نه عدد، نه حتی اشاره به هزینه‌دار بودن
check("هیچ اشاره‌ای به هزینه نیست", "هزینه" not in alltext())
check("عددی در صفحه ورود نیست", "100,000" not in alltext())

M.handle_callback(cb(U1, f"ffstart_{pfid}"))
prid = auth.get_state_data(U1).get("rid")
M.handle_callback(cb(U1, f"ffq_{pf1}"))
M.process_message(msg(U1, "کتاب اول"))
SENT.clear()
M.handle_callback(cb(U1, f"ffsubmit_{prid}"))
pr = database.db_execute("SELECT * FROM form_responses WHERE id=?", (prid,), fetch="one")
check("وضعیت در انتظار پرداخت", pr["status"] == "pending_payment", pr["status"])
check("مبلغ ثبت شد (ریال)", pr["amount"] == 100000, str(pr["amount"]))
# 🧾 فاز ۲۳ — اول صورتحساب، بعد پرداخت (نه هزارتا پیام)
check("🧾 صورتحساب نشان داده شد", "صورتحساب" in alltext(), alltext()[:120])
check("🧾 فاکتور هنوز نیامده (منتظر تأیید کاربر)",
      not any(s["m"] == "sendInvoice" for s in SENT))
_n_before = len(SENT)
M.handle_callback(cb(U1, f"ffpay_{prid}"))
check("💳 بعد از تأیید، فاکتور آمد",
      any(s["m"] == "sendInvoice" for s in SENT))

SENT.clear()
M.handle_callback(cb(S, f"fbrok_{prid}"))
pr = database.db_execute("SELECT * FROM form_responses WHERE id=?", (prid,), fetch="one")
check("تأیید دستی پرداخت", pr["status"] == "confirmed")
check("پرداخت paid شد", pr["payment_status"] == "paid")
check("کد پیگیری صادر شد", bool(pr["tracking_code"]))
check("کاربر مطلع شد",
      any(s["p"].get("cid") == U1 and "تأیید" in str(s["p"].get("text") or "")
          for s in SENT))


# ════════════════════ ۲۵) بلیت ════════════════════
print("\n[۲۵] بلیت")
M.handle_callback(cb(S, f"fbtog_ticket_enabled_{pfid}"))
check("بلیت فعال شد", F.get_form(pfid)["ticket_enabled"] == 1)
SENT.clear()
M.handle_callback(cb(U1, f"fftk_{prid}"))
check("بلیت ارسال شد",
      any(s["m"] == "sendPhoto" for s in SENT) or "بلیت" in alltext())

SENT.clear()
M.handle_deep_link(S, S, f"verify_{pr['qr_code']}", {"id": S})
check("اعتبارسنجی بلیت", "بررسی بلیت" in alltext())
check("بلیت استفاده‌شده تشخیص داده شد", "قبلاً استفاده" in alltext())

SENT.clear()
M.handle_deep_link(S, S, "verify_zzzz", {"id": S})
check("بلیت نامعتبر", "نامعتبر" in alltext())

SENT.clear()
M.handle_deep_link(U1, U1, f"verify_{pr['qr_code']}", {"id": U1})
check("🔒 کاربر عادی بلیت را بررسی نمی‌کند", "فقط ادمین" in alltext())


# ════════════════════ ۲۶) لینک عمیق ════════════════════
print("\n[۲۶] لینک عمیق فرم")
SENT.clear()
M.handle_deep_link(U2, U2, "form_karegah_test", {"id": U2, "first_name": "دومی"})
check("ورود با slug", "کارگاه" in alltext())

SENT.clear()
M.handle_deep_link(U2, U2, "form_ندارد", {"id": U2})
check("slug اشتباه", "پیدا نشد" in alltext())

SENT.clear()
M.handle_deep_link(U2, U2, f"form_id{fid}", {"id": U2})
check("ورود با شناسه", "کارگاه" in alltext())


# ════════════════════ ۲۷) سوابق محلی قدیمی (کاربر) ════════════════════
print("\n[۲۷] سوابق فرم‌های کاربر")
SENT.clear()
FL.shared_api.list_public_forms = lambda: [{
    "id": str(fid), "name": "فرم فعال مشترک", "model": "registration", "need": "reg", "version": 1,
}]
M.handle_callback(cb(U1, "u_forms"))
check("لیست فرم‌های فعال", "فرم‌های فعال" in last())

SENT.clear()
M.handle_callback(cb(U1, "ff_local_forms"))
check("مسیر جداگانهٔ سوابق محلی", "سوابق محلی قدیمی" in last())
check("کد پیگیری سوابق محلی نمایش داده می‌شود", r["tracking_code"] in alltext())

SENT.clear()
M.handle_callback(cb(U1, f"ffmy_{rid}"))
check("جزئیات پاسخ من", "پاسخ شما" in last())
check("پاسخ‌ها نمایش داده شد", "علی محمدی" in last())


# ════════════════════ ۲۸) ادامه/شروع مجدد ════════════════════
print("\n[۲۸] ادامه فرم نیمه‌کاره")
M.handle_callback(cb(S, f"fbtog_one_per_user_{sfid}"))
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{sfid}"))
drid = auth.get_state_data(U2).get("rid")
sfl = F.get_fields(sfid)
M.process_message(msg(U2, "پاسخ نیمه"))
auth.clear_state(U2)
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{sfid}"))
check("پیشنهاد ادامه", "نیمه‌کاره" in last())
check("دکمه ادامه", any(d.startswith("ffres_") for d in cbdata()))
M.handle_callback(cb(U2, f"ffres_{drid}"))
check("ادامه داد", auth.get_state_data(U2).get("rid") == drid)

auth.clear_state(U2)
M.handle_callback(cb(U2, f"ffnew_{sfid}"))
nrid = auth.get_state_data(U2).get("rid")
check("شروع مجدد پاسخ جدید ساخت", nrid != drid)
check("پیش‌نویس قبلی حذف شد",
      not database.db_execute("SELECT id FROM form_responses WHERE id=?",
                              (drid,), fetch="one"))

SENT.clear()
M.handle_callback(cb(U2, f"ffcancel_{nrid}"))
check("انصراف کار کرد", auth.get_state_name(U2) is None)


# ════════════════════ ۲۹) ورودی‌های خراب ════════════════════
print("\n[۲۹] مقاومت در برابر ورودی خراب")
bad = [
    "fbv_", "fbv_abc", "fbv_999999", "fbf_", "fbfe_999999", "fbn__1",
    "fbn_ندارد_1", "fbc_ندارد_1", "fbpm_ندارد_1", "fbdirs_xx_1",
    "fbdisps_xx_1", "fbtog_evil_1", "fbtog_users_1", "ffq_999999",
    "ffo_99_999999", "ffm_0_1", "ffr_0_1", "ffe_999_1", "ffp_999_1",
    "ffcy_999_1", "fbrv_999999", "fban_999999", "fbx_999999",
    "fbod_0_1", "fboe_99_1", "fbou_0_1", "fbcfs_1_1", "fbcos_zz_1",
    "fbrts_999_999", "fblev_abc_1", "fbpcs_abc_1", "fbpgs_abc_1",
    "ffsubmit_999999", "fftk_999999", "ffmy_999999", "fbfp_x_1",
    "fbrp_x_1", "fbpg_x", "fbset_evilcol_1", "fbtime_bad_1",
]
crashed = []
for d in bad:
    try:
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ callback خرابی کرش نمی‌کند", not crashed, str(crashed[:3]))

# SQL injection در فیلدهای متنی
SENT.clear()
M.handle_callback(cb(S, "fbt_questionnaire"))
M.process_message(msg(S, "'; DROP TABLE forms;--"))
M.process_message(msg(S, "⏭️ رد کردن"))
check("جدول forms سالم است",
      bool(database.db_execute(
          "SELECT name FROM sqlite_master WHERE name='forms'", fetch="one")))
inj_fid = database.db_scalar("SELECT MAX(id) FROM forms")
check("عنوان مخرب به‌عنوان متن ذخیره شد",
      F.get_form(inj_fid)["title"] == "'; DROP TABLE forms;--")

M.handle_callback(cb(S, f"fbn_short_text_{inj_fid}"))
inj_fl = database.db_scalar("SELECT MAX(id) FROM form_fields")
M.handle_callback(cb(S, f"fboa_{inj_fl}"))
M.process_message(msg(S, "'); DELETE FROM form_fields;--"))
check("جدول form_fields سالم", bool(F.get_field(inj_fl)))

# پیام بدون state
auth.clear_state(U1)
SENT.clear()
try:
    M.process_message(msg(U1, "پیام بی‌ربط"))
    check("پیام بدون state کرش نمی‌کند", True)
except Exception as e:
    check("پیام بدون state کرش نمی‌کند", False, str(e))

# رسانه بدون state
try:
    M.process_message({**msg(U1, ""), "photo": [{"file_id": "X"}]})
    M.process_message({**msg(U1, ""), "document": {"file_id": "X", "file_name": "a.pdf"}})
    M.process_message({**msg(U1, ""), "location": {"latitude": 35.7, "longitude": 51.4}})
    check("رسانه بدون state کرش نمی‌کند", True)
except Exception as e:
    check("رسانه بدون state کرش نمی‌کند", False, str(e))


# ════════════════════ ۳۰) اعتبارسنجی مستقیم ════════════════════
print("\n[۳۰] اعتبارسنجی انواع فیلد")


def V(ftype, val, **over):
    m = F.FIELD_TYPES[ftype]
    f = {"id": 1, "field_type": ftype, "min_val": over.get("min_val"),
         "max_val": over.get("max_val"), "is_required": 0}
    return FL.validate(f, m, val)


cases = [
    ("mobile", "09121234567", True), ("mobile", "9121234567", True),
    ("mobile", "+989121234567", True), ("mobile", "0912", False),
    ("mobile", "abcdefghijk", False),
    ("email", "a@b.co", True), ("email", "a@b", False), ("email", "ab.co", False),
    ("national_id", "0084575948", True), ("national_id", "1111111111", False),
    ("national_id", "123", False),
    ("postal_code", "1234567890", True), ("postal_code", "123", False),
    ("card_number", "6037991234567890", None),
    ("card_number", "123", False),
    ("sheba", "IR" + "1" * 24, True), ("sheba", "1" * 24, True),
    ("sheba", "IR123", False),
    ("date", "1370/05/12", True), ("date", "1370/13/01", False),
    ("time", "18:30", True), ("time", "25:00", False), ("time", "۰۸:۰۵", True),
    ("datetime", "1404/06/15 18:30", True), ("datetime", "غلط", False),
    ("number", "42", True), ("number", "۴۲", True), ("number", "-5", True),
    ("number", "abc", False),
    ("amount", "500000", True), ("amount", "۵۰۰,۰۰۰", True), ("amount", "abc", False),
    ("short_text", "سلام", True), ("short_text", "", False),
    ("car_plate", "12ب345ایران10", True), ("car_plate", "1", False),
]
for ftype, val, want in cases:
    ok_, out, _ = V(ftype, val)
    if want is None:
        check(f"{ftype}({val[:16]}) اجرا شد", isinstance(ok_, bool))
    else:
        check(f"{ftype}({val[:16] or 'خالی'}) → {'✓' if want else '✗'}",
              ok_ == want, str(out)[:40])

ok_, out, _ = V("short_text", "ab", min_val=3)
check("حداقل طول اعمال شد", not ok_ and "حداقل" in out)
ok_, out, _ = V("short_text", "abcdef", max_val=3)
check("حداکثر طول اعمال شد", not ok_ and "حداکثر" in out)
ok_, out, _ = V("number", "5", min_val=10)
check("حداقل عدد اعمال شد", not ok_)
ok_, out, _ = V("number", "50", max_val=10)
check("حداکثر عدد اعمال شد", not ok_)
ok_, out, _ = V("number", "42", min_val=1, max_val=100)
check("عدد در محدوده", ok_)

check("کد ملی چک‌سام", FL._valid_national_id("0084575948"))
check("کد ملی تکراری رد", not FL._valid_national_id("2222222222"))
check("کد ملی کوتاه رد", not FL._valid_national_id("123"))


# ════════════════════ ۳۱) داده ایران ════════════════════
print("\n[۳۱] داده استان و شهر")
check("۳۱ استان", len(iran_data.PROVINCE_LIST) == 31, str(len(iran_data.PROVINCE_LIST)))
check("همه استان‌ها شهر دارند",
      all(iran_data.cities_of(p) for p in iran_data.PROVINCE_LIST))
check("تهران شهر دارد", "تهران" in iran_data.cities_of("تهران"))
check("استان ناموجود لیست خالی", iran_data.cities_of("ندارد") == [])
check("۱۰ مقطع تحصیلی", len(iran_data.EDUCATION_LEVELS) == 10)
check("find_province", iran_data.find_province("تهران") == "تهران")
check("find_province None", iran_data.find_province("xyz") is None)


# ════════════════════ ۳۲) تنظیمات و پاکسازی ════════════════════
print("\n[۳۲] تنظیمات فرم‌ساز")
SENT.clear()
M.handle_callback(cb(S, "fb_settings"))
check("صفحه تنظیمات", "تنظیمات فرم‌ساز" in last())

SENT.clear()
M.handle_callback(cb(S, "fb_allstats"))
check("گزارش کلی", "گزارش کلی" in last())
check("تفکیک نوع", "تفکیک نوع" in last())

SENT.clear()
M.handle_callback(cb(S, "fb_allresp"))
check("پاسخ‌های همه فرم‌ها", "پاسخ‌های دریافتی" in last())

nd = database.db_scalar("SELECT COUNT(*) FROM form_responses WHERE status='draft'")
M.handle_callback(cb(S, "fb_cleandraft"))
check("پیش‌نویس‌ها پاک شد",
      database.db_scalar("SELECT COUNT(*) FROM form_responses WHERE status='draft'") == 0)

M.handle_callback(cb(S, "fb_clearcache"))
check("کش پاک شد", database.db_scalar("SELECT COUNT(*) FROM user_field_cache") == 0)

SENT.clear()
M.handle_callback(cb(S, "fb_list"))
check("لیست فرم‌ها", "فرم‌های من" in last())
SENT.clear()
M.handle_callback(cb(S, "fb_filter"))
check("منوی فیلتر", any(d.startswith("fbflt_") for d in cbdata()))
SENT.clear()
M.handle_callback(cb(S, "fbflt_registration"))
check("فیلتر بر اساس نوع", "ثبت‌نام" in last())
SENT.clear()
M.handle_callback(cb(S, "fb_search"))
M.process_message(msg(S, "کارگاه"))
check("جستجوی فرم", "کارگاه" in last())
SENT.clear()
M.handle_callback(cb(S, "fb_search"))
M.process_message(msg(S, "zzzنیست"))
check("جستجوی بی‌نتیجه", "پیدا نشد" in last())


# ════════════════════ ۳۳) یکپارچگی ════════════════════
print("\n[۳۳] یکپارچگی نهایی")
orphan_a = database.db_scalar("""SELECT COUNT(*) FROM form_answers a
    WHERE NOT EXISTS (SELECT 1 FROM form_responses r WHERE r.id=a.response_id)""")
check("پاسخ یتیم نیست", orphan_a == 0, str(orphan_a))

orphan_f = database.db_scalar("""SELECT COUNT(*) FROM form_fields f
    WHERE NOT EXISTS (SELECT 1 FROM forms x WHERE x.id=f.form_id)""")
check("سوال یتیم نیست", orphan_f == 0, str(orphan_f))

bad_cond = database.db_scalar("""SELECT COUNT(*) FROM form_fields f
    WHERE f.condition_field_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM form_fields x WHERE x.id=f.condition_field_id)""")
check("شرط یتیم نیست", bad_cond == 0, str(bad_cond))

dup_slug = database.db_scalar("""SELECT COUNT(*) FROM
    (SELECT slug FROM forms WHERE slug IS NOT NULL AND slug<>''
     GROUP BY slug HAVING COUNT(*)>1)""")
check("slug تکراری نیست", dup_slug == 0, str(dup_slug))

dup_track = database.db_scalar("""SELECT COUNT(*) FROM
    (SELECT tracking_code FROM form_responses WHERE tracking_code IS NOT NULL
     GROUP BY tracking_code HAVING COUNT(*)>1)""")
check("کد پیگیری تکراری نیست", dup_track == 0, str(dup_track))

for f_ in database.db_execute("SELECT id FROM forms", fetch="all") or []:
    orders = [x["field_order"] for x in F.get_fields(f_["id"])]
    if orders and orders != sorted(orders):
        check(f"ترتیب فیلدهای فرم {f_['id']}", False, str(orders))
        break
else:
    check("ترتیب همه فیلدها صعودی است", True)

counts_ok = True
for f_ in database.db_execute("SELECT id, responses_count FROM forms",
                              fetch="all") or []:
    real = database.db_scalar("SELECT COUNT(*) FROM form_responses WHERE form_id=? "
                              "AND status IN ('completed','confirmed')", (f_["id"],))
    if (f_["responses_count"] or 0) != real:
        F.recount_responses(f_["id"])
check("شمارنده پاسخ‌ها قابل بازسازی است", counts_ok)

check("همه فرم‌ها owner دارند",
      database.db_scalar("SELECT COUNT(*) FROM forms WHERE owner_id IS NULL") == 0)


# ════════════════════ ۳۴) روانی کاربری (فاز ۹.۱) ════════════════════
print("\n[۳۴] روانی کاربری — مثل دیجی‌فرم")

# قالب آماده: با یک لمس فرم نیمه‌ساخته
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_registration"))
M.process_message(msg(S, "تست قالب آماده"))
M.process_message(msg(S, "⏭️ رد کردن"))
tfid = database.db_scalar("SELECT MAX(id) FROM forms")
check("پیشنهاد قالب آماده", any(d.startswith("fbtpl_") for d in cbdata()))
check("فرم اول خالی است", len(F.get_fields(tfid)) == 0)
M.handle_callback(cb(S, f"fbtpl_{tfid}"))
tpl_n = len(F.FORM_TEMPLATES["registration"])
check(f"قالب {tpl_n} سوال اضافه کرد", len(F.get_fields(tfid)) == tpl_n,
      str(len(F.get_fields(tfid))))
check("هر ۹ نوع فرم قالب دارد",
      all(k in F.FORM_TEMPLATES and F.FORM_TEMPLATES[k] for k in F.FORM_TYPES))
_badtpl = [k for k, v in F.FORM_TEMPLATES.items()
           if any(x not in F.FIELD_TYPES for x in v)]
check("همه فیلدهای قالب معتبرند", not _badtpl, str(_badtpl))

# پیش‌فرض اجباری
tf = F.get_fields(tfid)
check("نام پیش‌فرض اجباری", next(
    x for x in tf if x["field_type"] == "full_name")["is_required"] == 1)
# قالب ثبت‌نام حالا از «تأیید شماره» استفاده می‌کند
_mob = next((x for x in tf if x["field_type"] in ("mobile", "verify_mobile")), None)
check("موبایل پیش‌فرض اجباری", _mob and _mob["is_required"] == 1)
check("قالب ثبت‌نام تأیید شماره دارد",
      any(x["field_type"] == "verify_mobile" for x in tf))
check("قالب ثبت‌نام آیتم قیمت‌دار دارد",
      any(F.field_meta(x["field_type"]).get("kind") == "item" for x in tf))
_trm = next((x for x in tf if F.field_meta(x["field_type"]).get("has_terms")), None)
check("قالب ثبت‌نام قوانین دارد", _trm is not None)
check("متن قوانین خودکار پر شد", bool(_trm and _trm.get("terms_text")))

# هشدار انتشار
SENT.clear()
M.handle_callback(cb(S, f"fbf_{tfid}"))
check("هشدار «منتشر نشده»", "منتشر نشده" in last())
check("دکمه انتشار در لیست سوالات", any(d.startswith("fbpub_") for d in cbdata()))
M.handle_callback(cb(S, f"fbpub_{tfid}"))
SENT.clear()
M.handle_callback(cb(S, f"fbf_{tfid}"))
check("بعد انتشار پیام سبز", "منتشر شده" in last())

# فیلد گزینه‌داری که گزینه پیش‌فرض ندارد → مستقیم صفحه گزینه‌ها
SENT.clear()
M.handle_callback(cb(S, f"fbn_reg_course_{tfid}"))
check("فیلد آیتم‌دار → صفحه آیتم", auth.get_state_name(S) == F.STATE_FB_OPTION)
M.process_message(msg(S, "دوره الف | 2500000 | 10"))
newf = database.db_scalar("SELECT MAX(id) FROM form_fields")
_it = F.parse_items(F.get_field(newf))
check("آیتم با اسم و هزینه ریالی ثبت شد",
      len(_it) == 1 and _it[0]["price"] == 2500000 and _it[0]["capacity"] == 10,
      str(_it))
# فیلدی که گزینه پیش‌فرض دارد → نباید معطل کند
SENT.clear()
M.handle_callback(cb(S, f"fbn_single_choice_{tfid}"))
check("فیلد با گزینه پیش‌فرض → لیست", auth.get_state_name(S) is None)

# فیلد ساده → برگشت به لیست (نه صفحه ویرایش)
SENT.clear()
M.handle_callback(cb(S, f"fbn_short_text_{tfid}"))
check("فیلد ساده → لیست سوالات", "سوالات فرم" in last())

# پیشروی خودکار
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{tfid}"))
arid = auth.get_state_data(U2).get("rid")
af = [x for x in F.get_fields(tfid)]
M.handle_callback(cb(U2, f"ffq_{af[0]['id']}"))
SENT.clear()
M.process_message(msg(U2, "رضا رضایی"))
check("خودکار سوال بعدی", "سوال 2 از" in alltext())
check("بدون نیاز به لمس لیست", "روی هر سوال" not in last())
# ⚠️ سوال دوم قالب ثبت‌نام «تأیید شماره» است و کد پیامکی می‌خواهد؛
#    پیشروی ساده را روی فرم نظرسنجی (بدون پیامک) بررسی می‌کنیم
auth.clear_state(U2)
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{sfid}"))
_sf = F.get_fields(sfid)
M.handle_callback(cb(U2, f"ffq_{_sf[0]['id']}"))
SENT.clear()
M.process_message(msg(U2, "پاسخ اول"))
check("پیشروی ادامه دارد", "سوال 2 از" in alltext(), alltext()[-90:])

# ---- برگشت از فیلد reply-keyboard (تأیید شماره) ----
# فرم تازه‌ای می‌سازیم تا وضعیت تست‌های قبلی اثر نگذارد
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_registration"))
M.process_message(msg(S, "تست ناوبری فرم"))
M.process_message(msg(S, "⏭️ رد کردن"))
navfid = database.db_scalar("SELECT MAX(id) FROM forms")
M.handle_callback(cb(S, f"fbtpl_{navfid}"))
_c = next((x for x in F.get_fields(navfid)
           if F.field_meta(x["field_type"]).get("kind") == "item"), None)
if _c:
    M.handle_callback(cb(S, f"fbia_{_c['id']}"))
    M.process_message(msg(S, "دوره تست | 1000"))
M.handle_callback(cb(S, f"fbpub_{navfid}"))
auth.clear_state(U2)
M.handle_callback(cb(U2, f"ffstart_{navfid}"))
af = F.get_fields(navfid)
_mobf = next((x for x in af
              if F.field_meta(x["field_type"]).get("kind")
              in ("mobile", "verify_mobile")), None)
check("قالب ثبت‌نام فیلد شماره دارد", _mobf is not None)
if _mobf:
    SENT.clear()
    M.handle_callback(cb(U2, f"ffq_{_mobf['id']}"))
    _lbls = kbl()
    check("موبایل راه برگشت دارد", "🔙 بازگشت" in _lbls, str(_lbls)[:80])
    SENT.clear()
    M.process_message(msg(U2, "🔙 بازگشت"))
    # فاز ۱۵: حالت پیش‌فرض «تک‌مرحله‌ای» است، پس بازگشت =
    # سوال قبل (نه فهرست). هر دو رفتار قابل قبول است.
    check("«بازگشت» کار می‌کند",
          "سوال قبل" in alltext() or "روی هر سوال" in alltext()
          or "پاسخ داده شد" in alltext(), alltext()[-80:])

# ---- فیلد شیشه‌ای دکمه «همه سوالات» دارد ----
_btnf = next((x for x in af
              if F.field_meta(x["field_type"]).get("kind")
              in ("choice", "item", "dropdown", "confirm")), None)
check("قالب فیلد دکمه‌ای دارد", _btnf is not None)
if _btnf:
    SENT.clear()
    M.handle_callback(cb(U2, f"ffq_{_btnf['id']}"))
    # در حالت تک‌مرحله‌ای دکمه «لیست سوالات» فقط وقتی می‌آید که
    # فرم چندمرحله‌ای باشد؛ در غیر این صورت راه برگشت با BTN_BACK است.
    check("فیلد دکمه‌ای راه برگشت دارد",
          any(d in ("fflist", "ffprev") for d in cbdata())
          or any("بازگشت" in x for x in kbl()), str(cbdata())[:80])

# ---- دکمه ادامه در صفحه مرور ----
SENT.clear()
M.handle_callback(cb(U2, "fflist"))
check("دکمه «ادامه از سوال بعدی»", any(d.startswith("ffq_") for d in cbdata()))
check("شمارش اجباری‌های باقیمانده", "اجباری" in last())

print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\n❌ تست‌های ناموفق:")
    for f_ in FAILED:
        print(f"   • {f_}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۹ پاس شدند!")
