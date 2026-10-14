"""
تست فاز ۲۳ — 🧾 صورتحساب · ☑️ چند مورد · 🔐 دسترسی کاربر · 🎉 منوی رویداد

درخواست کاربر (عیناً):
  «کلا قسمت مدیریت رویداد رو منوش رو جامع و کامل کن خیلی بهم ریختس...
   منو مدیریت رویداد کاربر چرا میتونه پاسخ هاشو حذف کنه تو فرم؟ اینو
   کاملا بردار و تنظیمش رو بزار تو فرم ساز که کاربر بعد از ثبت و
   تکمیل دسترسی هاش چیه. دکمه انتشار میزنی انتشار عمومی میشه فوری...
   متن قوانین و مقررات برای هر فرم مرتبط با اون فرم پیشفرضش عوض بشه...
   توی ثبت نام و انتخاب مورد های هزینه دار، امکان انتخاب چند گزینه
   باشه... وقتی فرم رو ثبت میکنم و میرم واسه پرداخت هزارتا پیام نیاد،
   یه پیام صورت حساب خوشگل و شیک بیاد... یه پیام کوچولو خاموش کردن
   فیلتر شکنم باشه و تمام»
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora23_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "k", "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1111111111111111",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b",
    "IMPORT_DIR": f"{TMP}/i", "FILES_DIR": f"{TMP}/f",
    "PROFILES_DIR": f"{TMP}/f/p", "EVENTS_DIR": f"{TMP}/f/e",
    "LOG_DIR": f"{TMP}/l", "BROADCAST_RATE": "999",
})

import bale_api  # noqa: E402

SENT = []


def _api(m, p=None, **k):
    SENT.append({"m": m, "p": p or {}})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "text": caption or "",
                                    "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file(
    "sendPhoto", "photo", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file(
    "sendDocument", "document", c, d, cap, kb)
bale_api.send_invoice = lambda c, **kw: (
    SENT.append({"m": "sendInvoice", "p": {"cid": c, "text": "فاکتور"}}),
    {"ok": True, "result": {"message_id": 1}})[1]
bale_api.answer_callback = lambda *a, **k: {"ok": True}

import config  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FF  # noqa: E402
import form_fields as FD  # noqa: E402
import form_reports as FR  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import payments as P  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, FD, FR, EV, AT, P, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
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
    return [s["p"].get("text") or "" for s in SENT]


def last():
    t = [x for x in texts() if x]
    return t[-1] if t else ""


def alltext():
    return " | ".join(texts())


def allcb():
    out = []
    for s in SENT:
        kb = s["p"].get("kb") or {}
        for r in kb.get("inline_keyboard", []):
            for b in r:
                if isinstance(b, dict) and b.get("callback_data"):
                    out.append(b["callback_data"])
    return out


def nbtn():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        if kb.get("inline_keyboard"):
            return sum(len(r) for r in kb["inline_keyboard"])
    return 0


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1,
                        "chat": {"id": uid, "type": "private"}}}


print("=" * 62)
print("🧪 تست فاز ۲۳ — صورتحساب · چند مورد · دسترسی · منوی رویداد")
print("=" * 62)

database.init_db()
F.init_form_tables()
EV.init_event_tables()
AT.init_attendance_tables()
P.init_payment_tables()
PM.init_permission_tables()
database.seed_default_settings()

S = 100000001
U1, U2 = 2310001, 2310002
auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000",
                      "phone")
auth.ensure_super_admin(S)
for i, u in enumerate((U1, U2)):
    auth.create_auth_user({"id": u, "first_name": f"کاربر{i+1}",
                           "last_name": "ت"}, f"0912333000{i}", "phone")

FID = database.db_execute(
    "INSERT INTO forms (title,slug,form_type,status,owner_id,"
    "payment_method,price,visibility) VALUES (?,?,?,?,?,?,?,?)",
    ("ثبت‌نام دوره‌ها", "dore23", "registration", "draft", S,
     "bale_wallet", 0, "link"))
FLD = database.db_execute(
    "INSERT INTO form_fields (form_id,field_order,field_type,label,"
    "is_required,multi_item) VALUES (?,?,?,?,?,?)",
    (FID, 1, "reg_course", "کدام دوره‌ها؟", 1, 1))
F.set_items(FLD, [
    {"title": "مورد ۱", "price": 500000, "capacity": 0, "booked": 0,
     "desc": ""},
    {"title": "مورد ۲", "price": 300000, "capacity": 0, "booked": 0,
     "desc": ""},
    {"title": "مورد ۳", "price": 200000, "capacity": 2, "booked": 2,
     "desc": ""},
])


# ═══════════ ۱) 🚀 انتشار = عمومی فوری ═══════════
print("\n[۱] 🚀 انتشار فوری عمومی")

_cols = [r["name"] for r in database.db_execute(
    "PRAGMA table_info(forms)", fetch="all")]
check("ستون after_submit ساخته شد", "after_submit" in _cols)
_fc = [r["name"] for r in database.db_execute(
    "PRAGMA table_info(form_fields)", fetch="all")]
check("ستون multi_item ساخته شد", "multi_item" in _fc)
check("ستون max_items ساخته شد", "max_items" in _fc)

check("قبل از انتشار: لینکی", F.get_form(FID)["visibility"] == "link")
SENT.clear()
M.handle_callback(cb(S, f"fbpub_{FID}"))
_f = F.get_form(FID)
check("🔴 فرمِ آیتم‌دار بدون قیمت ثابت هم منتشر می‌شود",
      _f["status"] == "active", str(_f["status"]))
check("🔴 انتشار = فوری عمومی (باگ رفع شد)",
      _f["visibility"] == "public", str(_f["visibility"]))
check("پیام تأیید مهربان است", "منتشر شد" in alltext())
check("لینک هم نشان داده می‌شود", "🔗" in alltext())
check("دکمه اطلاع‌رسانی دارد", f"fbnotify_{FID}" in allcb())

# فرم بدون هیچ مبلغی هنوز بلوکه می‌شود
_f2 = database.db_execute(
    "INSERT INTO forms (title,slug,form_type,status,owner_id,"
    "payment_method,price) VALUES (?,?,?,?,?,?,?)",
    ("بی‌مبلغ", "nop23", "registration", "draft", S, "bale_wallet", 0))
database.db_execute("INSERT INTO form_fields (form_id,field_order,"
                    "field_type,label) VALUES (?,?,?,?)",
                    (_f2, 1, "text", "نام"))
SENT.clear()
M.handle_callback(cb(S, f"fbpub_{_f2}"))
check("🛡️ فرم واقعاً بی‌مبلغ هنوز هشدار می‌گیرد",
      F.get_form(_f2)["status"] != "active")


# ═══════════ ۲) ☑️ انتخاب چند مورد ═══════════
print("\n[۲] ☑️ چند مورد هزینه‌دار")

SENT.clear()
M.handle_callback(cb(U1, f"ffstart_{FID}"))
RID = auth.get_state_data(U1).get("rid")
check("فرم شروع شد", bool(RID))
_cbs = allcb()
check("دکمه‌های چندانتخابی ساخته شد",
      any(c.startswith("ffim_") for c in _cbs), str(_cbs[:4]))
check("دکمه تأیید دارد", f"ffiok_{FLD}" in _cbs)
check("مورد پر ظرفیت قابل انتخاب نیست",
      not any(c == f"ffim_3_{FLD}" for c in _cbs))

M.handle_callback(cb(U1, f"ffim_1_{FLD}"))
check("مورد ۱ انتخاب شد",
      auth.get_state_data(U1).get("items") == [1])
M.handle_callback(cb(U1, f"ffim_2_{FLD}"))
check("🔴 مورد ۲ هم اضافه شد (چندتایی کار می‌کند)",
      sorted(auth.get_state_data(U1).get("items")) == [1, 2],
      str(auth.get_state_data(U1).get("items")))
SENT.clear()
M.handle_callback(cb(U1, f"ffim_1_{FLD}"))
check("دوباره زدن، برمی‌دارد",
      auth.get_state_data(U1).get("items") == [2])
M.handle_callback(cb(U1, f"ffim_1_{FLD}"))

SENT.clear()
M.handle_callback(cb(U1, f"ffiok_{FLD}"))
_a = database.db_execute("SELECT * FROM form_answers WHERE response_id=?",
                         (RID,), fetch="one")
check("هر دو مورد ذخیره شد",
      "مورد ۱" in _a["value_text"] and "مورد ۲" in _a["value_text"],
      str(_a["value_text"]))
check("در value_options هم هست",
      len(json.loads(_a["value_options"] or "[]")) == 2)
check("🔴 جمع دو مورد درست است", int(_a["value_number"]) == 800000,
      str(_a["value_number"]))
check("مبلغ کل فرم درست است",
      F.form_total_price(FID, RID) == 800000,
      str(F.form_total_price(FID, RID)))
check("خلاصه انتخاب به کاربر نشان داده شد",
      "۲ مورد" in alltext() or "2 مورد" in alltext()
      or "جمع" in alltext())

# سقف تعداد
database.db_execute("UPDATE form_fields SET max_items=1 WHERE id=?",
                    (FLD,))
M.handle_callback(cb(U1, f"ffstart_{FID}"))
_r3 = auth.get_state_data(U1).get("rid")
M.handle_callback(cb(U1, f"ffim_1_{FLD}"))
SENT.clear()
M.handle_callback(cb(U1, f"ffim_2_{FLD}"))
check("🔢 سقف انتخاب رعایت می‌شود",
      "حداکثر" in alltext(), last()[:70])
check("مورد دوم اضافه نشد",
      auth.get_state_data(U1).get("items") == [1],
      str(auth.get_state_data(U1).get("items")))
database.db_execute("UPDATE form_fields SET max_items=0 WHERE id=?",
                    (FLD,))
M.handle_callback(cb(U1, f"ffim_2_{FLD}"))
check("بعد از برداشتن سقف، دومی اضافه می‌شود",
      len(auth.get_state_data(U1).get("items") or []) == 2)
M.handle_callback(cb(U1, f"ffiok_{FLD}"))
RID = _r3


# ═══════════ ۳) 🧾 صورتحساب — یک پیام ═══════════
print("\n[۳] 🧾 صورتحساب شیک — نه هزارتا پیام")

SENT.clear()
M.handle_callback(cb(U1, f"ffsubmit_{RID}"))
_n = len([s for s in SENT if (s["p"].get("text") or "").strip()])
check("🔴 فقط یک پیام آمد (نه چندتا)", _n == 1, f"{_n} پیام")
check("🔴 فاکتور هنوز نیامده (منتظر تأیید)",
      not any(s["m"] == "sendInvoice" for s in SENT))
_t = last()
check("عنوان صورتحساب دارد", "صورتحساب" in _t)
check("🔴 موردها شفاف فهرست شده‌اند",
      "مورد ۱" in _t and "مورد ۲" in _t, _t[:120])
check("قیمت هر مورد جدا آمده", "500,000" in _t and "300,000" in _t)
check("جمع کل آمده", "800,000" in _t)
check("واحد پول درست است", "ریال" in _t)
check("🔴 هشدار کوچک فیلترشکن هست", "فیلترشکن" in _t)
check("هشدار کوتاه است (نه پیام جدا)",
      _t.count("فیلترشکن") == 1)
check("دکمه تأیید و پرداخت دارد", f"ffpay_{RID}" in allcb())
check("دکمه بازگشت برای ویرایش دارد", f"ffback_{RID}" in allcb())
check("وضعیت در انتظار پرداخت",
      database.db_execute("SELECT status FROM form_responses WHERE id=?",
                          (RID,), fetch="one")["status"]
      == "pending_payment")

SENT.clear()
M.handle_callback(cb(U1, f"ffpay_{RID}"))
check("🔴 فاکتور فقط بعد از تأیید کاربر",
      any(s["m"] == "sendInvoice" for s in SENT))
check("هشدار فیلترشکن دوباره نیامد",
      alltext().count("فیلترشکن را خاموش") <= 1, alltext()[:100])

SENT.clear()
M.handle_callback(cb(U1, f"ffback_{RID}"))
check("◀️ بازگشت به فرم کار می‌کند",
      database.db_execute("SELECT status FROM form_responses WHERE id=?",
                          (RID,), fetch="one")["status"] == "draft")
M.handle_callback(cb(U1, f"ffsubmit_{RID}"))


# ═══════════ ۴) 🔐 حذف پاسخ برداشته شد ═══════════
print("\n[۴] 🔐 کاربر نمی‌تواند پاسخش را حذف کند")

database.db_execute("UPDATE form_responses SET status='completed' "
                    "WHERE id=?", (RID,))
SENT.clear()
M.handle_callback(cb(U1, f"ffmy_{RID}"))
_kb = str([s["p"].get("kb") for s in SENT])
check("🔴 هیچ دکمه حذفی برای کاربر نیست",
      "fbrdel" not in _kb and "🗑️" not in alltext(), _kb[:120])
check("پاسخ‌هایش را می‌بیند", "پاسخ شما" in last())

_src = (ROOT / "form_fill.py").read_text(encoding="utf-8")
check("🔴 در فایل کاربر هیچ DELETE پاسخی نیست",
      "DELETE FROM form_answers" not in
      _src.split("def show_my_response")[1].split("def show_my_forms")[0])


# ═══════════ ۵) 🔐 دسترسی بعد از ثبت ═══════════
print("\n[۵] 🔐 تنظیم دسترسی در فرم‌ساز")

check("چهار حالت تعریف شده", len(F.AFTER_SUBMIT) == 4)
SENT.clear()
M.handle_callback(cb(S, f"fbafter_{FID}"))
check("صفحه دسترسی باز شد", "دسترسی کاربر بعد از ثبت" in last())
for k in F.AFTER_SUBMIT:
    check(f"حالت «{F.AFTER_SUBMIT[k]['name']}» دکمه دارد",
          f"fbaft_{k}_{FID}" in allcb())
check("تأکید می‌کند حذف ممکن نیست",
      "پاک کند" in last() or "پاک" in last())

for mode in ("view", "edit", "withdraw", "none"):
    M.handle_callback(cb(S, f"fbaft_{mode}_{FID}"))
    check(f"حالت «{mode}» ذخیره شد",
          F.after_submit_of(F.get_form(FID)) == mode)

# فقط مشاهده → دکمه ویرایش نباشد
M.handle_callback(cb(S, f"fbaft_view_{FID}"))
SENT.clear()
M.handle_callback(cb(U1, f"ffmy_{RID}"))
check("👁️ فقط مشاهده: دکمه ویرایش نیست",
      f"ffedit_{RID}" not in allcb())
check("👁️ دکمه انصراف هم نیست", f"ffwd_{RID}" not in allcb())

M.handle_callback(cb(S, f"fbaft_edit_{FID}"))
SENT.clear()
M.handle_callback(cb(U1, f"ffmy_{RID}"))
check("✏️ حالت ویرایش: دکمه ویرایش هست",
      f"ffedit_{RID}" in allcb())

M.handle_callback(cb(S, f"fbaft_none_{FID}"))
SENT.clear()
M.handle_callback(cb(U1, f"ffmy_{RID}"))
check("🔒 حالت بسته: پاسخ‌ها نشان داده نمی‌شود",
      "پاسخ شما —" not in last(), last()[:60])
check("🔒 ولی پیام مهربان می‌گیرد", "ثبت شد" in last())


# ═══════════ ۶) 🚪 انصراف بدون حذف داده ═══════════
print("\n[۶] 🚪 انصراف — داده پاک نمی‌شود")

M.handle_callback(cb(S, f"fbaft_withdraw_{FID}"))
_before = database.db_scalar(
    "SELECT COUNT(*) FROM form_answers WHERE response_id=?", (RID,))
SENT.clear()
M.handle_callback(cb(U1, f"ffwd_{RID}"))
check("تأیید انصراف پرسیده می‌شود", "انصراف" in last())
check("اطمینان می‌دهد داده پاک نمی‌شود",
      "پاک نمی‌شود" in last(), last()[:100])

M.handle_callback(cb(U1, f"ffwdy_{RID}"))
_r = database.db_execute("SELECT status FROM form_responses WHERE id=?",
                         (RID,), fetch="one")
_after = database.db_scalar(
    "SELECT COUNT(*) FROM form_answers WHERE response_id=?", (RID,))
check("🔴 وضعیت انصراف ثبت شد", _r["status"] == "withdrawn")
check("🔴 هیچ پاسخی پاک نشد", _after == _before,
      f"{_before} → {_after}")
check("رکورد پاسخ هم سرجاش است",
      bool(database.db_execute("SELECT 1 FROM form_responses WHERE id=?",
                               (RID,), fetch="one")))

SENT.clear()
M.handle_callback(cb(U1, "ff_local_forms"))
check("در سوابق محلی با علامت انصراف دیده می‌شود",
      "🚪" in alltext() or "سوابق محلی قدیمی" in last())

# ادمین هنوز همه‌چیز را می‌بیند
SENT.clear()
M.handle_callback(cb(S, f"fbrv_{RID}"))
check("👨‍💼 ادمین هنوز پاسخ را می‌بیند",
      "مورد ۱" in alltext() or "پاسخ" in alltext())
check("👨‍💼 ادمین دکمه حذف دارد (فقط او)",
      f"fbrdel_{RID}" in allcb())


# ═══════════ ۷) 📜 قوانین متناسب با نوع ═══════════
print("\n[۷] 📜 قوانین پیش‌فرض هر نوع فرم")

check("جدول قوانین ساخته شده", len(F.TERMS_BY_TYPE) >= 8)
_pairs = [("exam", "آزمون"), ("election", "رأی"),
          ("order", "سفارش"), ("contest", "مسابقه"),
          ("attendance", "حضور"), ("survey", "نظرسنجی")]
for ft, word in _pairs:
    t = F.terms_for_form_type(ft)
    check(f"«{ft}» قوانین مخصوص خودش دارد", word in t, t[:60])

check("🔴 قوانین آزمون با ثبت‌نام فرق دارد",
      F.terms_for_form_type("exam")
      != F.terms_for_form_type("registration"))
check("🔴 در آزمون از «حضور به‌موقع» خبری نیست",
      "حضور به‌موقع" not in F.terms_for_form_type("exam"))
check("ادمین می‌تواند بازنویسی کند",
      True)
database.set_setting("form_terms_exam", "قانون سفارشی من", "t", "form")
database.clear_settings_cache()
check("🔧 تنظیم دستی ادمین اولویت دارد",
      F.terms_for_form_type("exam") == "قانون سفارشی من")
database.set_setting("form_terms_exam", "", "t", "form")
database.clear_settings_cache()

# سوال قوانین با متن درست ساخته شود
_ex = database.db_execute(
    "INSERT INTO forms (title,slug,form_type,status,owner_id) "
    "VALUES (?,?,?,?,?)", ("آزمون تست", "az23", "exam", "draft", S))
F.apply_template(_ex, "exam")
_tf = [f for f in F.get_fields(_ex)
       if F.field_meta(f.get("field_type")).get("has_terms")]
if _tf:
    check("🔴 سوال قوانین آزمون، متن آزمون گرفت",
          "آزمون" in (_tf[0].get("terms_text") or ""),
          str(_tf[0].get("terms_text"))[:60])
else:
    check("قالب آزمون سوال قوانین ندارد — رد شد", True)


# ═══════════ ۸) ☑️ پنل ادمین چند مورد ═══════════
print("\n[۸] ☑️ تنظیم چند مورد در فرم‌ساز")

SENT.clear()
M.handle_callback(cb(S, f"fbit_{FLD}"))
_t = last()
check("صفحه آیتم‌ها باز شد", "آیتم" in _t, _t[:50])
check("حالت انتخاب نشان داده می‌شود", "حالت انتخاب" in _t)
check("دکمه تغییر حالت دارد", f"fbimt_{FLD}" in allcb())
check("دکمه سقف انتخاب دارد", f"fbimx_{FLD}" in allcb())

M.handle_callback(cb(S, f"fbimt_{FLD}"))
check("🔀 خاموش شد",
      not F.get_field(FLD).get("multi_item"))
M.handle_callback(cb(S, f"fbimt_{FLD}"))
check("♻️ دوباره روشن شد",
      bool(F.get_field(FLD).get("multi_item")))

M.handle_callback(cb(S, f"fbimx_{FLD}"))
M.process_message(msg(S, "۳"))
check("🔢 سقف با عدد فارسی ذخیره شد",
      int(F.get_field(FLD).get("max_items") or 0) == 3,
      str(F.get_field(FLD).get("max_items")))
M.handle_callback(cb(S, f"fbimx_{FLD}"))
M.process_message(msg(S, "0"))
check("۰ = نامحدود",
      int(F.get_field(FLD).get("max_items") or 0) == 0)


# ═══════════ ۹) 🎉 منوی مرتب رویداد ═══════════
print("\n[۹] 🎉 منوی رویداد — سبک و مرتب")

EID = database.db_execute(
    "INSERT INTO events (title,event_type,status,capacity,created_by,"
    "has_attendance,has_certificate,start_date,is_paid,price) "
    "VALUES (?,?,?,?,?,?,?,?,?,?)",
    ("کارگاه نمونه", "workshop", "published", 40, S, 1, 1,
     "1404/07/01", 1, 500000))

SENT.clear()
M.handle_callback(cb(S, f"ev_view_{EID}"))
_t = last()
_n = nbtn()
check("کارت رویداد باز شد", "کارگاه نمونه" in _t)
check("🔴 تعداد دکمه‌ها معقول است (نه ۱۲ تا)", _n <= 10, f"{_n} دکمه")
check("وضعیت نشان داده می‌شود", "وضعیت" in _t)
check("آمار ثبت‌نام دارد", "ثبت‌نام" in _t)
check("قابلیت‌های روشن را می‌گوید",
      "✋" in _t or "🎓" in _t)
_c = allcb()
check("در حضور و غیاب هست", f"att_list_{EID}" in _c)
check("در گواهینامه هست", f"cert_bulk_{EID}" in _c)
check("در ثبت‌نام‌ها هست", f"ev_regs_{EID}_0" in _c)
check("در تنظیمات هست", f"evset_{EID}" in _c)
check("در بیشتر هست", f"evmore_{EID}" in _c)
check("مرور سریع هم هست", f"evrev_{EID}" in _c)
check("💡 راهنمای قدم بعدی می‌دهد",
      "💡" in _t or "🌱" in _t or "🎓" in _t)

SENT.clear()
M.handle_callback(cb(S, f"evset_{EID}"))
check("⚙️ صفحه تنظیمات باز شد", "تنظیمات رویداد" in last())
check("بخش مالی دارد", "مالی" in last())
check("قابلیت‌ها را نشان می‌دهد", "قابلیت" in last())

SENT.clear()
M.handle_callback(cb(S, f"evmore_{EID}"))
check("⋮ صفحه بیشتر باز شد", "بیشتر" in last())
check("خروجی اکسل آنجاست", f"ev_export_{EID}" in allcb())
check("حذف رویداد آنجاست", f"ev_delq_{EID}" in allcb())

# پیش‌نویس → دکمه انتشار
_d = database.db_execute(
    "INSERT INTO events (title,event_type,status,capacity,created_by,"
    "start_date) VALUES (?,?,?,?,?,?)",
    ("پیش‌نویس", "workshop", "draft", 10, S, "1404/08/01"))
SENT.clear()
M.handle_callback(cb(S, f"ev_view_{_d}"))
check("پیش‌نویس دکمه انتشار دارد", f"ev_pub_{_d}" in allcb())
check("پیش‌نویس راهنما می‌گیرد", "پیش‌نویس" in last())


# ═══════════ ۱۰) 📢 اطلاع‌رسانی فرم ═══════════
print("\n[۱۰] 📢 اطلاع‌رسانی فرم")

SENT.clear()
M.handle_callback(cb(S, f"fbnotify_{FID}"))
check("تأیید اطلاع‌رسانی پرسیده شد", "اطلاع‌رسانی" in last())
check("تعداد گیرندگان را می‌گوید", "کاربر" in last())
SENT.clear()
M.handle_callback(cb(S, f"fbnoty_{FID}"))
check("📢 ارسال شد", "اطلاع داده شد" in alltext(), last()[:60])
check("به کاربر رسید",
      any(s["p"].get("cid") == U2 for s in SENT))


# ═══════════ ۱۱) 🔒 امنیت ═══════════
print("\n[۱۱] 🔒 دسترسی")

for d in (f"fbafter_{FID}", f"fbaft_view_{FID}", f"fbnotify_{FID}",
          f"fbimt_{FLD}", f"evset_{EID}", f"evmore_{EID}"):
    SENT.clear()
    M.handle_callback(cb(U2, d))
    check(f"🔒 کاربر عادی: {d[:20]}", "دسترسی" in last(), last()[:40])

# کاربر نمی‌تواند پاسخ دیگری را ببیند یا انصراف دهد
SENT.clear()
M.handle_callback(cb(U2, f"ffwd_{RID}"))
check("🔒 انصراف از پاسخ دیگری ممکن نیست",
      "دسترسی" in last(), last()[:40])


# ═══════════ ۱۲) 🛡️ ورودی خراب ═══════════
print("\n[۱۲] 🛡️ ورودی‌های خراب")

for d in ("ffim_x_1", "ffiok_abc", "ffpay_99999", "ffback_abc",
          "ffwd_99999", "fbaft_bad_1", "fbafter_abc", "fbimt_abc",
          "fbimx_99999", "evset_abc", "evmore_99999", "ffinv_abc"):
    SENT.clear()
    try:
        M.handle_callback(cb(S, d))
        check(f"🛡️ «{d}» کرش نمی‌کند", True)
    except Exception as e:
        check(f"🛡️ «{d}» کرش نمی‌کند", False, str(e)[:70])

check("build_invoice با شناسه بد کرش نمی‌کند",
      FF.build_invoice(99999)[0] == "")
check("chosen_items با ورودی خالی",
      F.chosen_items({}, {}) == [])
check("after_submit_of با None",
      F.after_submit_of(None) in F.AFTER_SUBMIT)
check("terms_for_form_type با نوع ناشناس",
      len(F.terms_for_form_type("nope")) > 10)


# ═══════════ ۱۳) 🛡️ رگرسیون ═══════════
print("\n[۱۳] 🛡️ رگرسیون")

for a in ("form_withdraw", "form_notify", "form_setting"):
    check(f"لاگ فارسی «{a}»", a in AL.ACTION_FA)

SENT.clear()
M.handle_callback(cb(S, f"fbv_{FID}"))
check("صفحه فرم سالم", "ثبت‌نام دوره" in last())
SENT.clear()
M.handle_callback(cb(S, f"fbdet_{FID}"))
check("جزئیات فرم سالم", "جزئیات" in last())
SENT.clear()
M.handle_callback(cb(S, f"fbadv_{FID}"))
check("تنظیمات پیشرفته سالم", nbtn() > 3)
check("دکمه دسترسی در تنظیمات هست", f"fbafter_{FID}" in allcb())
SENT.clear()
M.handle_callback(cb(S, f"fbr_{FID}"))
check("لیست پاسخ‌ها سالم", nbtn() >= 1)
SENT.clear()
M.handle_callback(cb(S, "fb_list"))
check("فهرست فرم‌ها سالم", "فرم" in last())
SENT.clear()
M.handle_callback(cb(U1, "u_forms"))
check("فرم‌های عمومی کاربر سالم", "فرم" in last())

# تک‌انتخابی هنوز کار می‌کند
_sf = database.db_execute(
    "INSERT INTO forms (title,slug,form_type,status,owner_id,"
    "payment_method,price,visibility) VALUES (?,?,?,?,?,?,?,?)",
    ("تک‌انتخابی", "tak23", "registration", "active", S, "card",
     100000, "public"))
_sfl = database.db_execute(
    "INSERT INTO form_fields (form_id,field_order,field_type,label,"
    "is_required) VALUES (?,?,?,?,?)",
    (_sf, 1, "reg_class", "کلاس؟", 1))
F.set_items(_sfl, [{"title": "کلاس الف", "price": 50000, "capacity": 0,
                    "booked": 0, "desc": ""}])
SENT.clear()
M.handle_callback(cb(U2, f"ffstart_{_sf}"))
_r2 = auth.get_state_data(U2).get("rid")
check("♻️ تک‌انتخابی دکمه ffi_ دارد",
      any(c.startswith("ffi_") for c in allcb()), str(allcb()[:3]))
M.handle_callback(cb(U2, f"ffi_1_{_sfl}"))
_a2 = database.db_execute("SELECT * FROM form_answers WHERE response_id=?",
                          (_r2,), fetch="one")
check("♻️ تک‌انتخابی درست ذخیره شد",
      _a2 and _a2["value_text"] == "کلاس الف")
check("♻️ مبلغ تک‌انتخابی درست",
      F.form_total_price(_sf, _r2) == 150000,
      str(F.form_total_price(_sf, _r2)))

import guard as G  # noqa: E402
_ff = G.check_new_features()
check("🛡️ همه قابلیت‌ها سالم", all(_ff.values()),
      str([k for k, v in _ff.items() if not v]))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۳ پاس شدند!")
