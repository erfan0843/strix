"""
تست فاز ۱۵ — روان‌سازی فرم و رویداد + تکمیل موارد باقی‌مانده

درخواست‌های کاربر:
  ۱) فرم پیش‌فرض تک‌مرحله‌ای (هر مرحله یک سوال)
  ۲) بازپرداخت رویداد پیش‌فرض خاموش
  ۳) وقتی «نمایش مبلغ» خاموش است، هیچ عددی به کاربر نشان داده نشود
  ۴) بعد از پیش‌نویس رویداد: انتخاب فرم / پروفایل / فرم قبلی
  ۵) مرور تنظیمات پیشرفته در پایان ویزارد (رویداد و فرم)
  ۶) موارد باقی‌مانده: خوش‌آمد، گواهینامه فرم، آیدی کارت، ارتباط،
     اسپانسر/گالری، غیبت مجاز
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora15_")
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
import auth  # noqa: E402
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
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, PAY, EV, AT, OC, AL, CL, TK, LT, AD, M):
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


def kblabels():
    out = []
    for s in SENT:
        kb = s["p"].get("kb") or {}
        for r in kb.get("inline_keyboard", []):
            for b in r:
                if isinstance(b, dict):
                    out.append(b.get("text") or "")
    return out


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


_sl = [0]


def mkform(owner, ftype, title, **kw):
    _sl[0] += 1
    cols = {"owner_id": owner, "form_type": ftype, "title": title,
            "slug": f"s{_sl[0]}", "status": "draft"}
    cols.update(kw)
    ks = list(cols)
    return database.db_execute(
        f"INSERT INTO forms ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])


S = 100000001
U1, U2 = 950001, 950002

print("=" * 62)
print("🧪 تست فاز ۱۵ — روان‌سازی + تکمیل")
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
LT.init_lottery_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
auth.create_auth_user({"id": U1, "first_name": "علی"}, "09131111111", "phone")
auth.create_auth_user({"id": U2, "first_name": "سارا"}, "09132222222", "phone")


# ═══════════ ۱) فرم تک‌مرحله‌ای پیش‌فرض ═══════════
print("\n[۱] 1️⃣ فرم تک‌مرحله‌ای پیش‌فرض")

fid = mkform(S, "questionnaire", "فرم تست")
form = F.get_form(fid)
check("پیش‌فرض display_mode = one_by_one",
      form.get("display_mode") == "one_by_one",
      str(form.get("display_mode")))

col = [c for c in database.db_execute("PRAGMA table_info(forms)", fetch="all")
       if c["name"] == "display_mode"][0]
check("DEFAULT ستون هم one_by_one است",
      "one_by_one" in str(col.get("dflt_value")), str(col.get("dflt_value")))

# fallback در کد
import re as _re
src = (ROOT / "form_fill.py").read_text(encoding="utf-8")
check("fallback در form_fill درست است",
      'or "user_choice")' not in src)
src2 = (ROOT / "forms.py").read_text(encoding="utf-8")
check("fallback در forms درست است",
      'DISPLAY_MODES["user_choice"])' not in src2)

# فرم بدون display_mode صریح → تک‌مرحله‌ای رفتار کند
database.db_execute("UPDATE forms SET display_mode=NULL WHERE id=?", (fid,))
f2 = F.get_form(fid)
mode = f2.get("display_mode") or "one_by_one"
check("فرم بدون مقدار → تک‌مرحله‌ای", mode == "one_by_one")
database.db_execute("UPDATE forms SET display_mode='one_by_one' WHERE id=?",
                    (fid,))


# ═══════════ ۲) بازپرداخت پیش‌فرض خاموش ═══════════
print("\n[۲] 💸 بازپرداخت پیش‌فرض خاموش")

eid = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "capacity, created_by) "
    "VALUES ('رویداد تست','workshop','draft',1,500000,50,?)", (S,))
ev = EV.get_event(eid)
check("refund_enabled پیش‌فرض ۰", not int(ev.get("refund_enabled") or 0),
      str(ev.get("refund_enabled")))

c2 = [c for c in database.db_execute("PRAGMA table_info(events)", fetch="all")
      if c["name"] == "refund_enabled"][0]
check("DEFAULT ستون هم ۰ است", str(c2.get("dflt_value")) == "0",
      str(c2.get("dflt_value")))


# ═══════════ ۳) 🔴 نمایش مبلغ خاموش = هیچ عددی ═══════════
print("\n[۳] 💰 نمایش مبلغ خاموش → هیچ عددی به کاربر")

database.db_execute("UPDATE events SET show_price_publicly=0, "
                    "status='published' WHERE id=?", (eid,))
ev = EV.get_event(eid)

check("تابع show_price موجود", hasattr(EV, "show_price"))
check("کاربر: مبلغ نبیند", not EV.show_price(ev))
check("ادمین: مبلغ ببیند", EV.show_price(ev, for_admin=True))

# متن کامل رویداد
body = EV.event_full_text(ev, for_admin=False)
check("🔴 عدد ۵۰۰٬۰۰۰ در متن کاربر نیست",
      "500" not in body and "۵۰۰" not in body, body[:150])
check("ولی می‌گوید هزینه دارد", "هزینه" in body, body[:100])

body_admin = EV.event_full_text(ev, for_admin=True)
# فاز ۱۷-ج: ۵۰۰۰۰۰ ریال ذخیره‌شده = ۵۰٬۰۰۰ تومان نمایش
check("✅ ادمین عدد را می‌بیند",
      "50" in body_admin or "۵۰" in body_admin, body_admin[:150])

# صفحه رویداد کاربر
SENT.clear()
EV.show_event_user(U1, U1, eid)
t = alltext()
check("🔴 صفحه رویداد کاربر بدون عدد",
      "500,000" not in t and "۵۰۰٬۰۰۰" not in t and "500000" not in t,
      t[:150])
check("دکمه ثبت‌نام بدون عدد",
      not any(_re.search(r"\d{3}", x) for x in kblabels()
              if "ثبت‌نام" in x), str(kblabels()))

# لیست رویدادها
SENT.clear()
EV.show_user_events(U1, U1, 0)
t2 = alltext()
check("🔴 لیست رویدادها بدون عدد",
      "500,000" not in t2 and "۵۰۰٬۰۰۰" not in t2, t2[:150])
check("ولی «هزینه‌دار» می‌گوید", "هزینه" in t2 or "💳" in t2, t2[:100])

# حالا روشن کنیم → عدد باید بیاید
database.db_execute("UPDATE events SET show_price_publicly=1 WHERE id=?",
                    (eid,))
ev = EV.get_event(eid)
body2 = EV.event_full_text(ev, for_admin=False)
check("✅ با روشن بودن، عدد نمایش داده می‌شود",
      "50" in body2 or "۵۰" in body2, body2[:150])
database.db_execute("UPDATE events SET show_price_publicly=0 WHERE id=?",
                    (eid,))

# کد تخفیف هم نباید عدد بدهد
database.db_execute("""INSERT INTO event_discount_codes
    (event_id, code, discount_type, amount, is_active, created_by)
    VALUES (?,'TEST10','percent',10,1,?)""", (eid, S))
SENT.clear()
EV.register(U2, U2, eid)
t3 = alltext()
check("🔴 صفحه کد تخفیف بدون مبلغ",
      "500,000" not in t3 and "۵۰۰٬۰۰۰" not in t3, t3[:150])
auth.clear_state(U2)
database.db_execute("DELETE FROM event_discount_codes WHERE event_id=?",
                    (eid,))
database.db_execute("DELETE FROM event_registrations WHERE event_id=?",
                    (eid,))


# ═══════════ ۴) دستیار بعد از ساخت رویداد ═══════════
print("\n[۴] 🧭 دستیار بعد از پیش‌نویس")

# فاز ۱۶: معماری ۴ گزینه‌ای طبق فایل (خط ۵۰۷۵۰)
check("۴ روش ثبت‌نام", len(EV.REG_MODES) == 4, str(list(EV.REG_MODES)))
for k in ("quick", "existing", "advanced", "none"):
    check(f"روش {k}", k in EV.REG_MODES)

SENT.clear()
M.handle_callback(cb(S, f"evwiz_{eid}"))
check("دستیار باز شد", "ثبت‌نام" in last(), last()[:50])
w = allcb()
check("گزینه فرم سریع", f"evrm_quick_{eid}" in w, str(w))
check("گزینه فرم موجود", f"evrm_existing_{eid}" in w)
check("گزینه فرم پیشرفته", f"evrm_advanced_{eid}" in w)
check("گزینه بدون فرم", f"evrm_none_{eid}" in w)
check("گزینه رد کردن", f"evrev_{eid}" in w)

# بدون فرم
SENT.clear()
M.handle_callback(cb(S, f"evrm_none_{eid}"))
check("بدون فرم انتخاب شد", "پروفایل" in alltext(), alltext()[:60])
check("به صفحه مرور رفت", "مرور" in last(), last()[:50])
ev = EV.get_event(eid)
check("registration_form_id پاک شد", not ev.get("registration_form_id"))

# فرم قبلی
fid2 = mkform(S, "registration", "فرم ثبت‌نام قدیمی", status="active")
# فاز ۱۶: فرم بدون سوال در لیست نمی‌آید — پس سوال اضافه می‌کنیم
database.db_execute("INSERT INTO form_fields (form_id, field_order, "
                    "field_type, label) VALUES (?,1,'full_name','نام')",
                    (fid2,))
SENT.clear()
M.handle_callback(cb(S, f"evrm_existing_{eid}"))
check("لیست فرم‌های قبلی", "فرم‌های شما" in last(), last()[:50])
check("فرم در لیست هست",
      any(d.startswith("evpick_") for d in allcb()), str(allcb()))

SENT.clear()
M.handle_callback(cb(S, f"evpick_{fid2}_{eid}"))
check("فرم وصل شد", "وصل شد" in alltext(), alltext()[:60])
ev = EV.get_event(eid)
check("registration_form_id ثبت شد",
      ev.get("registration_form_id") == fid2,
      str(ev.get("registration_form_id")))
f_linked = F.get_form(fid2)
check("🔗 اتصال دوطرفه (فرم→رویداد)", f_linked.get("event_id") == eid,
      str(f_linked.get("event_id")))

# فرم پیشرفته
SENT.clear()
M.handle_callback(cb(S, f"evrm_advanced_{eid}"))
check("فرم پیشرفته ساخته شد", "ساخته شد" in alltext(), alltext()[:60])
ev = EV.get_event(eid)
check("فرم پیشرفته وصل شد", bool(ev.get("registration_form_id")))
check("دکمه بازگشت به رویداد", f"evrev_{eid}" in allcb(), str(allcb())[:120])


# ═══════════ ۵) مرور تنظیمات رویداد ═══════════
print("\n[۵] 🔍 مرور تنظیمات رویداد")

SENT.clear()
M.handle_callback(cb(S, f"evrev_{eid}"))
check("صفحه مرور باز شد", "مرور نهایی" in last(), last()[:50])
r = allcb()
check("ظرفیت قابل تغییر", f"evcap_capacity_{eid}" in r, str(r))
check("روش ثبت‌نام قابل تغییر", f"evwiz_{eid}" in r)
check("تنظیمات پیشرفته‌تر", f"evx_{eid}" in r)

# فاز ۱۷: require_profile هم اضافه شد → ۸ تاگل
# فاز ۱۷-ج: hide_cost_hint هم اضافه شد → ۹ تاگل
check("۹ تاگل مرور", len(EV.REVIEW_TOGGLES) == 9,
      str(len(EV.REVIEW_TOGGLES)))
check("🙈 مخفی‌سازی هزینه در مرور",
      any(k == "hide_cost_hint" for k, _, _ in EV.REVIEW_TOGGLES))
check("👤 نیاز به پروفایل در مرور",
      any(k == "require_profile" for k, _, _ in EV.REVIEW_TOGGLES))
for key, _, _ in EV.REVIEW_TOGGLES:
    check(f"تاگل {key}", f"evtogr_{key}_{eid}" in r, str(r)[:100])

# تاگل از صفحه مرور → برگشت به مرور
before = int(EV.get_event(eid).get("has_attendance") or 0)
SENT.clear()
M.handle_callback(cb(S, f"evtogr_has_attendance_{eid}"))
after = int(EV.get_event(eid).get("has_attendance") or 0)
check("تاگل عمل کرد", before != after, f"{before}→{after}")
check("به صفحه مرور برگشت", "مرور نهایی" in last(), last()[:50])

# نمایش قیمت هم از همین‌جا
SENT.clear()
M.handle_callback(cb(S, f"evtogr_show_price_publicly_{eid}"))
check("نمایش قیمت از مرور عوض شد",
      int(EV.get_event(eid).get("show_price_publicly") or 0) == 1)
M.handle_callback(cb(S, f"evtogr_show_price_publicly_{eid}"))

# ویرایش ظرفیت
SENT.clear()
M.handle_callback(cb(S, f"evcap_capacity_{eid}"))
check("ویرایش ظرفیت شروع شد", "ظرفیت" in last(), last()[:40])
M.process_message(msg(S, "abc"))
check("🔒 ورودی غیرعددی رد شد", "عدد" in last(), last()[:40])
M.process_message(msg(S, "120"))
check("ظرفیت ذخیره شد",
      int(EV.get_event(eid).get("capacity") or 0) == 120,
      str(EV.get_event(eid).get("capacity")))
check("به مرور برگشت", "مرور نهایی" in last())

# پیش‌نویس → دکمه انتشار
database.db_execute("UPDATE events SET status='draft' WHERE id=?", (eid,))
SENT.clear()
M.handle_callback(cb(S, f"evrev_{eid}"))
check("پیش‌نویس دکمه انتشار دارد", f"ev_pub_{eid}" in allcb(),
      str(allcb()))
database.db_execute("UPDATE events SET status='published' WHERE id=?", (eid,))

# دکمه مرور در صفحه رویداد
SENT.clear()
EV.show_event_admin(S, S, eid)
check("🔍 دکمه مرور در صفحه رویداد", f"evrev_{eid}" in allcb())


# ═══════════ ۶) مرور تنظیمات فرم ═══════════
print("\n[۶] 🔍 مرور تنظیمات فرم")

database.db_execute("INSERT INTO form_fields (form_id, field_order, "
                    "field_type, label) VALUES (?,1,'short_text','نام')",
                    (fid,))

SENT.clear()
M.handle_callback(cb(S, f"fbrev_{fid}"))
check("صفحه مرور فرم", "مرور نهایی" in last(), last()[:50])
fr = allcb()
check("تعداد سوال نمایش داده شد", "سوالات" in last())
check("نحوه نمایش قابل تغییر", f"fbdisp_{fid}" in fr, str(fr))
check("سوالات قابل دسترس", f"fbf_{fid}" in fr)
check("پرداخت قابل دسترس", f"fbpay_{fid}" in fr)
check("پیشرفته‌تر", f"fbadv_{fid}" in fr)
check("دکمه انتشار", f"fbpub_{fid}" in fr)

check("۸ آیتم مرور فرم", len(F.FORM_REVIEW) == 8, str(len(F.FORM_REVIEW)))
for key, _, _ in F.FORM_REVIEW:
    if key == "display_mode":
        continue
    check(f"تاگل فرم {key}", f"fbtog_{key}_{fid}" in fr, str(fr)[:100])

# تاگل کار کند
b = int(F.get_form(fid).get("one_per_user") or 0)
M.handle_callback(cb(S, f"fbtog_one_per_user_{fid}"))
check("تاگل فرم عمل کرد",
      int(F.get_form(fid).get("one_per_user") or 0) != b)

# فرم بدون سوال → هشدار
fid3 = mkform(S, "questionnaire", "فرم خالی")
SENT.clear()
M.handle_callback(cb(S, f"fbrev_{fid3}"))
check("⛔ هشدار فرم بدون سوال", "سوالی ندارد" in last(), last()[:80])

# پرداخت بدون مبلغ → هشدار
database.db_execute("UPDATE forms SET payment_method='card', price=0 "
                    "WHERE id=?", (fid,))
SENT.clear()
M.handle_callback(cb(S, f"fbrev_{fid}"))
check("⛔ هشدار پرداخت بدون مبلغ", "مبلغ ندارد" in last(), last()[:100])
database.db_execute("UPDATE forms SET payment_method='none' WHERE id=?",
                    (fid,))

# دکمه اصلی فرم پیش‌نویس → مرور
SENT.clear()
F.show_form(S, S, fid)
check("دکمه «مرور و انتشار» در صفحه فرم",
      f"fbrev_{fid}" in allcb(), str(allcb())[:150])
check("انتشار مستقیم نیست", f"fbpub_{fid}" not in allcb())


# ═══════════ ۷) صفحه خوش‌آمدگویی ═══════════
print("\n[۷] 👋 صفحه خوش‌آمدگویی")

cols = {c["name"] for c in
        database.db_execute("PRAGMA table_info(forms)", fetch="all")}
for c in ("welcome_text", "cert_enabled", "idcard_enabled",
          "contact_enabled", "cert_template", "idcard_title"):
    check(f"ستون forms.{c}", c in cols)

check("welcome_text در INFO_FIELDS", "welcome_text" in F.INFO_FIELDS)

database.db_execute("UPDATE forms SET welcome_text=?, status='active' "
                    "WHERE id=?", ("👋 به فرم ما خوش آمدید!", fid))
SENT.clear()
FF.open_form(U1, U1, fid)
check("متن خوش‌آمد نمایش داده شد",
      "خوش آمدید" in alltext(), alltext()[:100])

database.db_execute("UPDATE forms SET welcome_text=NULL WHERE id=?", (fid,))
SENT.clear()
FF.open_form(U1, U1, fid)
check("بدون خوش‌آمد هم سالم کار می‌کند",
      "فرم" in alltext(), alltext()[:60])


# ═══════════ ۸) گواهینامه فرم و آیدی کارت ═══════════
print("\n[۸] 🎓 گواهینامه فرم · 🆔 آیدی کارت")

database.db_execute("""UPDATE forms SET cert_enabled=1, idcard_enabled=1,
    contact_enabled=1, idcard_title='کارت عضویت' WHERE id=?""", (fid,))
rid = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, tracking_code)
    VALUES (?,?,'completed','TRK123')""", (fid, U1))

SENT.clear()
M.handle_callback(cb(U1, f"ffcert_{rid}"))
check("گواهینامه صادر شد", "گواهینامه" in last(), last()[:60])
check("نام در گواهینامه", "علی" in last())
check("شماره پیگیری در گواهینامه", "TRK123" in last())

SENT.clear()
M.handle_callback(cb(U1, f"ffcard_{rid}"))
check("کارت صادر شد", "کارت عضویت" in last(), last()[:60])
check("نام روی کارت", "علی" in last())

# کاربر دیگر نباید ببیند
SENT.clear()
M.handle_callback(cb(U2, f"ffcert_{rid}"))
check("🔒 کاربر دیگر گواهینامه نمی‌گیرد", "دسترسی" in last() or "یافت" in last(),
      last()[:50])

# وقتی غیرفعال است
database.db_execute("UPDATE forms SET cert_enabled=0 WHERE id=?", (fid,))
SENT.clear()
M.handle_callback(cb(U1, f"ffcert_{rid}"))
check("🔒 گواهینامه خاموش → پیام مناسب", "گواهینامه ندارد" in last(), last()[:50])
database.db_execute("UPDATE forms SET cert_enabled=1 WHERE id=?", (fid,))

# دکمه‌ها در پنل تنظیمات فرم
SENT.clear()
F.show_advanced(S, S, fid)
adv = allcb()
check("👋 خوش‌آمد در پنل", f"fbset_welcome_text_{fid}" in adv, str(adv)[:150])
check("🎓 گواهینامه در پنل", f"fbtog_cert_enabled_{fid}" in adv)
check("🆔 کارت در پنل", f"fbtog_idcard_enabled_{fid}" in adv)
# 🔄 فاز ۴۰: «ارتباط» به لایهٔ دوم منتقل شد
SENT.clear()
F.show_advanced2(S, S, fid)
check("💬 ارتباط در پنل",
      f"fbtog_contact_enabled_{fid}" in allcb())


# ═══════════ ۹) ارتباط تکمیل‌کننده با ادمین ═══════════
print("\n[۹] 💬 ارتباط تکمیل‌کننده")

SENT.clear()
M.handle_callback(cb(U1, f"ffmsg_{rid}"))
check("درخواست پیام شروع شد", "پیام" in last(), last()[:50])
M.process_message(msg(U1, "سلام، سوالی داشتم"))
check("پیام ارسال شد", "ارسال شد" in alltext(), alltext()[:60])
check("به مالک فرم رسید",
      any("سوالی داشتم" in t for t in to(S)), str(to(S))[:100])

# لغو
SENT.clear()
M.handle_callback(cb(U1, f"ffmsg_{rid}"))
M.process_message(msg(U1, "🔙 بازگشت"))
check("لغو پیام کار کرد", "لغو" in last(), last()[:40])

# پیام خالی
SENT.clear()
M.handle_callback(cb(U1, f"ffmsg_{rid}"))
M.process_message(msg(U1, "   "))
check("🔒 پیام خالی رد شد", "بنویسید" in last(), last()[:40])
auth.clear_state(U1)


# ═══════════ ۱۰) محتوای تکمیلی رویداد ═══════════
print("\n[۱۰] 🏢 اسپانسر · گالری · محتوای آموزشی")

ecols = {c["name"] for c in
         database.db_execute("PRAGMA table_info(events)", fetch="all")}
for c in ("sponsors", "gallery", "materials", "trip_plan",
          "emergency_contacts"):
    check(f"ستون events.{c}", c in ecols)
    check(f"{c} در EV_TEXTS", c in EV.EV_TEXTS)

SENT.clear()
EV.show_content(S, S, eid)
cnt = allcb()
for c in ("sponsors", "gallery", "materials"):
    check(f"دکمه {c}", f"evtxt_{c}_{eid}" in cnt, str(cnt)[:150])

SENT.clear()
M.handle_callback(cb(S, f"evtxt_sponsors_{eid}"))
check("ویرایش اسپانسر شروع شد", "اسپانسر" in last(), last()[:40])
M.process_message(msg(S, "شرکت الف\nشرکت ب"))
check("اسپانسر ذخیره شد",
      "شرکت الف" in str(EV.get_event(eid).get("sponsors") or ""),
      str(EV.get_event(eid).get("sponsors")))


# ═══════════ ۱۱) غیبت مجاز ═══════════
print("\n[۱۱] 📄 درخواست غیبت مجاز")

tabs = {r["name"] for r in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")}
check("جدول excuse_requests", "excuse_requests" in tabs)

database.db_execute("UPDATE events SET has_attendance=1 WHERE id=?", (eid,))
database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'confirmed')""", (eid, auth.get_user(U1)["id"], U1))

SENT.clear()
M.handle_callback(cb(U1, "exq_new"))
check("انتخاب رویداد", "غیبت مجاز" in last(), last()[:50])
check("رویداد در لیست", f"exqe_{eid}" in allcb(), str(allcb()))

SENT.clear()
M.handle_callback(cb(U1, f"exqe_{eid}"))
check("درخواست دلیل", "دلیل" in last(), last()[:50])
M.process_message(msg(U1, "بیماری"))
check("درخواست ثبت شد", "ثبت شد" in alltext(), alltext()[:60])
check("ادمین خبردار شد",
      any("غیبت مجاز" in t for t in to(S)), str(to(S))[-120:])

exr = database.db_execute("SELECT * FROM excuse_requests WHERE bale_user_id=?",
                          (U1,), fetch="one")
check("در دیتابیس ذخیره شد", bool(exr))
check("وضعیت pending", exr and exr["status"] == "pending")
check("دلیل ذخیره شد", exr and exr["reason"] == "بیماری")

# لیست ادمین
SENT.clear()
M.handle_callback(cb(S, "ex_list"))
check("لیست درخواست‌ها", "غیبت مجاز" in last(), last()[:50])
check("دکمه تأیید", f"exok_{exr['id']}" in allcb())

# تأیید
database.db_execute("""INSERT INTO attendance_sessions
    (event_id, title, session_no, session_code, method, created_by)
    VALUES (?,'جلسه ۱',1,'AB123','code',?)""", (eid, S))
SENT.clear()
M.handle_callback(cb(S, f"exok_{exr['id']}"))
check("درخواست تأیید شد",
      database.db_execute("SELECT status FROM excuse_requests WHERE id=?",
                          (exr["id"],), fetch="one")["status"] == "approved")
check("به کاربر اطلاع رفت",
      any("تأیید شد" in t for t in to(U1)), str(to(U1))[-100:])
rec = database.db_execute("""SELECT * FROM attendance_records
    WHERE bale_user_id=? AND status='excused'""", (U1,), fetch="one")
check("رکورد «معذور» ثبت شد", bool(rec))

# تأیید دوباره
SENT.clear()
M.handle_callback(cb(S, f"exok_{exr['id']}"))
check("🔒 بررسی دوباره جلوگیری شد", "قبلاً" in last(), last()[:40])

# کاربر عادی نباید لیست ببیند
SENT.clear()
M.handle_callback(cb(U2, "ex_list"))
check("🔒 کاربر عادی لیست غیبت نمی‌بیند", "دسترسی" in last())

# دکمه در منوی کاربران ادمین
SENT.clear()
M.handle_callback(cb(S, "admin_users"))
check("📄 دکمه غیبت در مدیریت کاربران", "ex_list" in allcb(),
      str(allcb())[:150])


# ═══════════ ۱۲) ورودی‌های خراب ═══════════
print("\n[۱۲] 🛡️ ورودی‌های خراب")

bad = [
    "evwiz_", "evwiz_abc", "evwiz_999999",
    "evrev_", "evrev_abc", "evrev_999999",
    "evrm_", "evrm_evil_1", "evrm_profile_999999",
    "evpick_", "evpick_abc_1", "evpick_999999_1",
    "evcap_", "evcap_evil_1", "evcap_capacity_999999",
    "evtogr_", "evtogr_evil_1", "evtogr_is_admin_1",
    "fbrev_", "fbrev_abc", "fbrev_999999",
    "ffcert_", "ffcert_abc", "ffcert_999999",
    "ffcard_abc", "ffmsg_999999",
    "exq_new", "exqe_abc", "ex_list", "exok_abc", "exno_999999",
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
        M.handle_callback(cb(U2, d))
    except Exception as e:
        crashed2.append(f"{d}: {type(e).__name__} {e}")
check("کاربر عادی: هیچ کرشی", not crashed2, str(crashed2[:3]))

for st in (EV.STATE_EV_NUM, FF.STATE_FF_MSG, AT.STATE_ATT_EXCUSE):
    try:
        auth.set_state(S, st, {"eid": eid, "key": "capacity",
                               "fid": fid, "rid": rid}, merge=False)
        SENT.clear()
        M.process_message(msg(S, "!@#$%"))
    except Exception as e:
        check(f"state {st}", False, str(e))
auth.clear_state(S)
check("state های جدید سالم", True)


# ═══════════ ۱۳) لاگ فارسی ═══════════
print("\n[۱۳] 📋 لاگ فارسی")

_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))
for k in ("event_form_linked", "excuse_request", "excuse_reviewed",
          "form_cert", "form_idcard", "form_contact"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۱۴) رگرسیون ═══════════
print("\n[۱۴] ♻️ رگرسیون")

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
check("پنل ادمین سالم", "پنل ادمین" in last())
check("پنل خلوت مانده", len(allcb()) <= 8, str(len(allcb())))

SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
check("داشبورد گزارشات سالم", "داشبورد گزارشات" in last())

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
check("پرداخت و مالی سالم", "پرداخت" in last())

SENT.clear()
M.handle_callback(cb(S, f"lt_event_{eid}"))
check("قرعه‌کشی سالم", "قرعه‌کشی" in last())

SENT.clear()
M.handle_callback(cb(S, f"evx_{eid}"))
check("قابلیت‌های پیشرفته سالم", "پیشرفته" in last())

SENT.clear()
M.handle_callback(cb(S, f"fbadv_{fid}"))
check("تنظیمات پیشرفته فرم سالم", "پیشرفته" in last())

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر سالم", "نورا" in alltext() or "سلام" in alltext())

SENT.clear()
M.process_message(msg(S, "/start"))
check("start ادمین سالم", "نورا" in alltext() or "سلام" in alltext())

# پرداخت هنوز کار می‌کند
database.db_execute("UPDATE events SET payment_method='bale_wallet' "
                    "WHERE id=?", (eid,))
ev = EV.get_event(eid)
rid9 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid, auth.get_user(U2)["id"], U2))
SENT.clear()
PAY.route_payment(U2, U2, ev, rid9, 500000)
tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid9,), fetch="one")
check("♻️ پرداخت هنوز کار می‌کند", bool(tx))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۵ پاس شدند!")
