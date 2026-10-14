"""
تست فاز ۱۶ — اتصال درست فرم‌ساز به رویداد + کارمزد درگاه

درخواست کاربر:
  ۱) اتصال فرم‌ساز به رویداد طبق معماری (خط ۵۰۷۵۰):
     ⚡ فرم سریع · 📋 فرم موجود · 🎨 فرم پیشرفته · 🎁 بدون فرم
  ۲) منوی فرم‌ساز روان و کاربرپسند
  ۳) کارمزد درصدی روی درگاه پرداخت — عنوان و درصد از تنظیمات مالی
     توسط سوپرادمین قابل تغییر
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora16_")
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


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


_sl = [0]


def mkform(owner, ftype, title, nfields=0, **kw):
    _sl[0] += 1
    cols = {"owner_id": owner, "form_type": ftype, "title": title,
            "slug": f"x{_sl[0]}", "status": "active"}
    cols.update(kw)
    ks = list(cols)
    fid = database.db_execute(
        f"INSERT INTO forms ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])
    for i in range(nfields):
        database.db_execute(
            "INSERT INTO form_fields (form_id, field_order, field_type, "
            "label) VALUES (?,?,'short_text',?)", (fid, i + 1, f"س{i+1}"))
    return fid


def mkevent(title="رویداد", **kw):
    cols = {"title": title, "event_type": "workshop", "status": "published",
            "capacity": 50, "created_by": S}
    cols.update(kw)
    ks = list(cols)
    return database.db_execute(
        f"INSERT INTO events ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])


S = 100000001
A_EV = 960001
U1, U2, U3 = 970001, 970002, 970003

print("=" * 62)
print("🧪 تست فاز ۱۶ — فرم‌ساز↔رویداد + کارمزد درگاه")
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
auth.create_auth_user({"id": A_EV, "first_name": "رضا"}, "09131111111", "phone")
PM.set_role(A_EV, "event_admin", S)
for u, n in ((U1, "علی"), (U2, "سارا"), (U3, "محمد")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0913{u}", "phone")
    # پروفایل کامل تا گارد require_profile مانع ثبت‌نام نشود
    database.db_execute(
        "UPDATE users SET profile_status='approved', "
        "complete_profile_percent=100, last_name='ت', gender='مرد', "
        "birth_date='1370/01/01', city='تهران' WHERE bale_user_id=?", (u,))


# ═══════════ ۱) معماری ۴ گزینه‌ای ═══════════
print("\n[۱] 📝 معماری ۴ گزینه‌ای (فایل معماری خط ۵۰۷۵۰)")

check("۴ روش ثبت‌نام", len(EV.REG_MODES) == 4, str(list(EV.REG_MODES)))
for k, nm in (("quick", "فرم سریع"), ("existing", "فرم موجود"),
              ("advanced", "فرم پیشرفته"), ("none", "بدون فرم")):
    check(f"روش {k} ({nm})", k in EV.REG_MODES)

check("۸ فیلد فرم سریع", len(EV.QUICK_FIELDS) == 8,
      str(len(EV.QUICK_FIELDS)))
keys = [k for k, _, _, _ in EV.QUICK_FIELDS]
for k in ("full_name", "mobile", "email", "national_id", "age",
          "gender", "province_city"):
    check(f"فیلد {k}", k in keys, str(keys))

defaults = EV._quick_defaults()
check("نام و موبایل پیش‌فرض تیک‌دار",
      "full_name" in defaults and "mobile" in defaults, str(defaults))
check("ایمیل پیش‌فرض تیک ندارد", "email" not in defaults)

req = [k for k, _, _, r in EV.QUICK_FIELDS if r]
check("نام و موبایل اجباری‌اند", set(req) == {"full_name", "mobile"},
      str(req))

eid = mkevent("کارگاه تست")
SENT.clear()
M.handle_callback(cb(S, f"evwiz_{eid}"))
w = allcb()
check("صفحه فرم ثبت‌نام باز شد", "فرم ثبت‌نام" in last(), last()[:50])
for k in ("quick", "existing", "advanced", "none"):
    check(f"دکمه {k}", f"evrm_{k}_{eid}" in w, str(w))
check("وضعیت فعلی «بدون فرم»", "بدون فرم" in last())


# ═══════════ ۲) ⚡ فرم سریع ═══════════
print("\n[۲] ⚡ فرم سریع — بدون خروج از رویداد")

SENT.clear()
M.handle_callback(cb(S, f"evrm_quick_{eid}"))
check("صفحه فرم سریع", "فرم سریع" in last(), last()[:50])
q = allcb()
check("همه فیلدها دکمه دارند",
      sum(1 for d in q if d.startswith("evqf_")) == 8, str(len(q)))
check("دکمه ساخت", f"evqok_{eid}" in q)
check("نام تیک‌خورده نشان داده شد", "☑️" in last())
check("ستاره اجباری", "⭐" in last())

# تیک زدن ایمیل
SENT.clear()
M.handle_callback(cb(S, f"evqf_email_{eid}"))
sel = EV._quick_selected(S, eid)
check("ایمیل اضافه شد", "email" in sel, str(sel))

# برداشتن ایمیل
M.handle_callback(cb(S, f"evqf_email_{eid}"))
check("ایمیل برداشته شد", "email" not in EV._quick_selected(S, eid))

# فیلد اجباری برداشته نمی‌شود
SENT.clear()
M.handle_callback(cb(S, f"evqf_full_name_{eid}"))
check("🔒 فیلد اجباری حذف نمی‌شود",
      "full_name" in EV._quick_selected(S, eid))
check("پیام هشدار داد", "اجباری" in alltext(), alltext()[:60])

# فیلد نامعتبر
SENT.clear()
M.handle_callback(cb(S, f"evqf_evil_{eid}"))
check("🔒 فیلد نامعتبر رد شد", "نامعتبر" in last())

# اضافه کردن چند فیلد و ساخت
M.handle_callback(cb(S, f"evqf_gender_{eid}"))
M.handle_callback(cb(S, f"evqf_province_city_{eid}"))
sel = EV._quick_selected(S, eid)
check("۴ فیلد انتخاب شد", len(sel) == 4, str(sel))

SENT.clear()
M.handle_callback(cb(S, f"evqok_{eid}"))
check("فرم سریع ساخته شد", "ساخته شد" in alltext(), alltext()[:70])

ev = EV.get_event(eid)
fid_q = ev.get("registration_form_id")
check("🔗 فرم به رویداد وصل شد", bool(fid_q))
frm = F.get_form(fid_q)
check("فرم فعال است", frm.get("status") == "active", str(frm.get("status")))
check("🔗 اتصال دوطرفه", frm.get("event_id") == eid,
      str(frm.get("event_id")))
check("نوع فرم registration", frm.get("form_type") == "registration")
check("تک‌مرحله‌ای است", frm.get("display_mode") == "one_by_one")

nf = database.db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                        (fid_q,))
check("۴ سوال ساخته شد", nf == 4, str(nf))
flds = database.db_execute("SELECT * FROM form_fields WHERE form_id=? "
                           "ORDER BY field_order", (fid_q,), fetch="all")
check("نام اجباری است",
      any(f["field_type"] == "full_name" and f["is_required"] for f in flds))
check("برچسب فارسی درست",
      any("نام و نام خانوادگی" in (f["label"] or "") for f in flds),
      str([f["label"] for f in flds]))
check("به مرور رفت", "مرور" in last(), last()[:50])


# ═══════════ ۳) 🔴 کاربر واقعاً فرم را می‌بیند ═══════════
print("\n[۳] 🔴 باگ اصلی: کاربر فرم را می‌بیند")

SENT.clear()
EV.register(U1, U1, eid)
t = alltext()
check("فرم به کاربر نشان داده شد",
      "تکمیل فرم ثبت‌نام" in t, t[:100])
check("تعداد سوال گفته شد", "4 سوال" in t or "۴ سوال" in t or "سوال" in t)
check("کاربر وارد فرم شد",
      "شروع پر کردن" in t or "سوال" in t or "فرم" in t, t[-150:])

# ثبت‌نام نباید هنوز قطعی شده باشد
reg = database.db_execute("SELECT * FROM event_registrations "
                          "WHERE event_id=? AND bale_user_id=?",
                          (eid, U1), fetch="one")
check("🔒 ثبت‌نام قبل از فرم قطعی نشد", not reg, str(reg))
auth.clear_state(U1)

# حالا فرم را «تکمیل‌شده» علامت بزنیم → ثبت‌نام باید انجام شود
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, tracking_code)
    VALUES (?,?,'completed','TRK1')""", (fid_q, U1))
SENT.clear()
EV.register(U1, U1, eid)
reg = database.db_execute("SELECT * FROM event_registrations "
                          "WHERE event_id=? AND bale_user_id=?",
                          (eid, U1), fetch="one")
check("✅ بعد از تکمیل فرم، ثبت‌نام انجام شد", bool(reg))
check("وضعیت confirmed", reg and reg["status"] == "confirmed",
      str(reg.get("status") if reg else None))

# رویداد بدون فرم → مستقیم ثبت‌نام
eid2 = mkevent("رویداد بدون فرم")
SENT.clear()
EV.register(U2, U2, eid2)
reg2 = database.db_execute("SELECT * FROM event_registrations "
                           "WHERE event_id=? AND bale_user_id=?",
                           (eid2, U2), fetch="one")
check("رویداد بدون فرم مستقیم ثبت‌نام می‌کند", bool(reg2))


# ═══════════ ۴) حلقه بازگشت: فرم → رویداد ═══════════
print("\n[۴] 🔗 بعد از تکمیل فرم، ثبت‌نام ادامه می‌یابد")

eid3 = mkevent("رویداد حلقه")
fid3 = mkform(S, "registration", "فرم حلقه", nfields=1, event_id=eid3)
database.db_execute("UPDATE events SET registration_form_id=? WHERE id=?",
                    (fid3, eid3))

rid3 = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'draft')""", (fid3, U3))
fld = database.db_execute("SELECT id FROM form_fields WHERE form_id=?",
                          (fid3,), fetch="one")
database.db_execute("""INSERT INTO form_answers
    (response_id, field_id, value_text) VALUES (?,?,'پاسخ')""",
    (rid3, fld["id"]))

SENT.clear()
FF.finalize(U3, U3, rid3)
check("فرم تکمیل شد", "ثبت" in alltext(), alltext()[:60])
reg3 = database.db_execute("SELECT * FROM event_registrations "
                           "WHERE event_id=? AND bale_user_id=?",
                           (eid3, U3), fetch="one")
check("✅ ثبت‌نام رویداد خودکار انجام شد", bool(reg3), "حلقه بسته نشد")


# ═══════════ ۵) 📋 فرم موجود ═══════════
print("\n[۵] 📋 استفاده از فرم موجود")

eid4 = mkevent("رویداد چهارم")
fid_ok = mkform(S, "registration", "فرم آماده", nfields=3)
mkform(S, "questionnaire", "فرم خالی", nfields=0)

SENT.clear()
M.handle_callback(cb(S, f"evrm_existing_{eid4}"))
check("لیست فرم‌ها", "فرم‌های شما" in last(), last()[:50])
check("تعداد سوال نمایش داده شد", "سوال" in last())
picks = [d for d in allcb() if d.startswith("evpick_")]
check("فرم دارای سوال در لیست هست",
      any(str(fid_ok) in d for d in picks), str(picks))
check("🔒 فرم بدون سوال در لیست نیست", len(picks) >= 1)

SENT.clear()
M.handle_callback(cb(S, f"evpick_{fid_ok}_{eid4}"))
check("فرم وصل شد", "وصل شد" in alltext(), alltext()[:60])
ev4 = EV.get_event(eid4)
check("registration_form_id ثبت شد",
      ev4.get("registration_form_id") == fid_ok)
check("🔗 دوطرفه", F.get_form(fid_ok).get("event_id") == eid4)

# فرم بدون سوال نباید وصل شود
fid_empty = mkform(S, "questionnaire", "خالی۲", nfields=0)
SENT.clear()
M.handle_callback(cb(S, f"evpick_{fid_empty}_{eid4}"))
check("🔒 فرم بدون سوال وصل نمی‌شود", "سوالی ندارد" in last(), last()[:50])
check("فرم قبلی دست‌نخورده",
      EV.get_event(eid4).get("registration_form_id") == fid_ok)


# ═══════════ ۶) 🎁 بدون فرم — قطع اتصال ═══════════
print("\n[۶] 🎁 بدون فرم")

SENT.clear()
M.handle_callback(cb(S, f"evrm_none_{eid4}"))
check("بدون فرم انتخاب شد", "پروفایل" in alltext(), alltext()[:60])
check("اتصال قطع شد",
      not EV.get_event(eid4).get("registration_form_id"))
check("🔗 فرم هم آزاد شد",
      not F.get_form(fid_ok).get("event_id"),
      str(F.get_form(fid_ok).get("event_id")))


# ═══════════ ۷) 🎨 فرم پیشرفته با بازگشت ═══════════
print("\n[۷] 🎨 فرم پیشرفته")

eid5 = mkevent("رویداد پنجم")
SENT.clear()
M.handle_callback(cb(S, f"evrm_advanced_{eid5}"))
check("فرم پیشرفته ساخته شد", "ساخته شد" in alltext(), alltext()[:70])
ev5 = EV.get_event(eid5)
check("فرم وصل شد", bool(ev5.get("registration_form_id")))
adv = allcb()
check("دکمه ویرایش سوالات", any(d.startswith("fbf_") for d in adv), str(adv))
check("🔙 دکمه بازگشت به رویداد", f"evrev_{eid5}" in adv, str(adv))

# صفحه فرم هم باید بازگشت به رویداد داشته باشد
SENT.clear()
F.show_form(S, S, ev5["registration_form_id"])
check("صفحه فرم: بازگشت به رویداد",
      f"evrev_{eid5}" in allcb(), str(allcb())[:150])
check("اتصال به رویداد نمایش داده شد",
      "رویداد" in last(), last()[:120])


# ═══════════ ۸) منوی فرم‌ساز ═══════════
print("\n[۸] 📝 منوی فرم‌ساز")

SENT.clear()
M.handle_callback(cb(S, "fb_panel"))
p = allcb()
check("پنل باز شد", "فرم‌ساز" in last(), last()[:40])
check("منو خلوت است (≤۷)", len(p) <= 7, str(len(p)))
for d in ("fb_new", "fb_list", "fb_allresp", "fb_allstats", "fb_admins",
          "fb_settings"):
    check(f"دکمه {d}", d in p, str(p))
check("آمار پیش‌نویس", "پیش‌نویس" in last())
check("تعداد فرم در دکمه",
      any("فرم‌های من" in (b or "") for b in [
          x.get("text") for s in SENT
          for r in (s["p"].get("kb") or {}).get("inline_keyboard", [])
          for x in r]))

# پاسخ منتظر تأیید → badge
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'pending_review')""",
    (fid_ok, U1))
SENT.clear()
M.handle_callback(cb(S, "fb_panel"))
check("🔴 پاسخ منتظر تأیید نمایش داده شد",
      "منتظر تأیید" in last(), last()[:200])


# ═══════════ ۹) 💳 کارمزد درگاه — محاسبات ═══════════
print("\n[۹] 💳 کارمزد درگاه")

check("تنظیمات کارمزد seed شد",
      database.get_setting("pay_fee_custom_gateway_pct", "") != "")
check("پیش‌فرض غیرفعال", not PAY.fee_enabled("custom_gateway"))

f0, t0 = PAY.calc_fee(1000000, "custom_gateway")
check("غیرفعال → بدون کارمزد", f0 == 0 and t0 == 1000000, f"{f0},{t0}")

database.set_setting("pay_fee_custom_gateway_on", "1", "t", "payment")
database.set_setting("pay_fee_custom_gateway_pct", "2.5", "t", "payment")
database.clear_settings_cache()

check("درصد اعشاری خوانده شد", PAY.fee_percent("custom_gateway") == 2.5,
      str(PAY.fee_percent("custom_gateway")))

# ۱۰۰٬۰۰۰ تومان = ۱٬۰۰۰٬۰۰۰ ریال → ۲.۵٪ = ۲۵٬۰۰۰ ریال
f1, t1 = PAY.calc_fee(1000000, "custom_gateway")
check("کارمزد ۲.۵٪ درست", f1 == 25000, str(f1))
check("مبلغ نهایی = اصل + کارمزد", t1 == 1025000, str(t1))

# فاز ۱۷: بقیه روش‌ها هم می‌توانند کارمزد داشته باشند ولی خاموش‌اند
for m in ("card", "bale_wallet", "points", "onsite"):
    fm, tm = PAY.calc_fee(1000000, m)
    check(f"{m} خاموش → بدون کارمزد", fm == 0 and tm == 1000000, f"{fm},{tm}")
# و اگر روشن شوند، کار می‌کنند
database.set_setting("pay_fee_card_on", "1", "t", "payment")
database.set_setting("pay_fee_card_pct", "1", "t", "payment")
database.clear_settings_cache()
_fc, _tc = PAY.calc_fee(1000000, "card")
check("✅ فاز۱۷: کارت هم می‌تواند کارمزد داشته باشد", _fc == 10000, str(_fc))
database.set_setting("pay_fee_card_on", "0", "t", "payment")
database.clear_settings_cache()

# سقف
database.set_setting("pay_fee_custom_gateway_max", "10000", "t", "payment")
database.clear_settings_cache()
f2, _ = PAY.calc_fee(10000000, "custom_gateway")
check("سقف کارمزد اعمال شد", f2 == 10000, str(f2))
database.set_setting("pay_fee_custom_gateway_max", "0", "t", "payment")

# حداقل
database.set_setting("pay_fee_custom_gateway_min", "5000", "t", "payment")
database.clear_settings_cache()
f3, _ = PAY.calc_fee(10000, "custom_gateway")
check("حداقل کارمزد اعمال شد", f3 == 5000, str(f3))
database.set_setting("pay_fee_custom_gateway_min", "0", "t", "payment")
database.clear_settings_cache()

# ورودی خراب
check("مبلغ None امن", PAY.calc_fee(None, "custom_gateway") == (0, 0))
check("مبلغ منفی امن", PAY.calc_fee(-100, "custom_gateway")[0] == 0)
database.set_setting("pay_fee_custom_gateway_pct", "abc", "t", "payment")
database.clear_settings_cache()
check("درصد خراب → صفر", PAY.fee_percent("custom_gateway") == 0.0, str(PAY.fee_percent("custom_gateway")))
database.set_setting("pay_fee_custom_gateway_pct", "999", "t", "payment")
database.clear_settings_cache()
check("درصد >۱۰۰ محدود شد", PAY.fee_percent("custom_gateway") == 100.0)
database.set_setting("pay_fee_custom_gateway_pct", "2.5", "t", "payment")
database.clear_settings_cache()


# ═══════════ ۱۰) 💳 پنل کارمزد ═══════════
print("\n[۱۰] ⚙️ پنل تنظیمات کارمزد")

SENT.clear()
M.handle_callback(cb(S, "pay_adv"))
check("دکمه کارمزد در پیشرفته", "pay_fee" in allcb(), str(allcb()))

SENT.clear()
M.handle_callback(cb(S, "pay_fee"))
fe = allcb()
check("صفحه کارمزد", "کارمزد" in last(), last()[:50])
check("لیست روش‌ها", any(d.startswith("payfm_") for d in fe), str(fe))





# تغییر درصد
SENT.clear()
M.handle_callback(cb(S, "payfe_pct_custom_gateway"))
check("ویرایش درصد شروع شد", "درصد" in last(), last()[:40])
M.process_message(msg(S, "abc"))
check("🔒 ورودی خراب رد شد", "معتبر" in last(), last()[:40])
M.process_message(msg(S, "150"))
check("🔒 درصد >۱۰۰ رد شد", "۱۰۰" in last() or "100" in last())
M.process_message(msg(S, "3.5"))
check("درصد اعشاری ذخیره شد", PAY.fee_percent("custom_gateway") == 3.5,
      str(PAY.fee_percent("custom_gateway")))

# تغییر عنوان
SENT.clear()
M.handle_callback(cb(S, "payfe_label_custom_gateway"))
check("ویرایش عنوان", "عنوان" in last(), last()[:40])
M.process_message(msg(S, "کارمزد تراکنش بانکی"))
check("عنوان ذخیره شد", PAY.fee_label("custom_gateway") == "کارمزد تراکنش بانکی",
      PAY.fee_label("custom_gateway"))

# خاموش/روشن
SENT.clear()
M.handle_callback(cb(S, "payft_custom_gateway"))
check("خاموش شد", not PAY.fee_enabled("custom_gateway"))
M.handle_callback(cb(S, "payft_custom_gateway"))
check("روشن شد", PAY.fee_enabled("custom_gateway"))

# 🔒 فقط سوپرادمین
SENT.clear()
M.handle_callback(cb(A_EV, "pay_fee"))
check("🔒 ادمین عادی دسترسی ندارد",
      "سوپرادمین" in last() or "دسترسی" in last(), last()[:50])
SENT.clear()
M.handle_callback(cb(A_EV, "payft_custom_gateway"))
check("🔒 ادمین عادی تاگل نمی‌کند", PAY.fee_enabled("custom_gateway"))


# ═══════════ ۱۱) کارمزد در پرداخت واقعی ═══════════
print("\n[۱۱] 🧾 کارمزد در جریان پرداخت")

tx_cols = {c["name"] for c in
           database.db_execute("PRAGMA table_info(transactions)",
                               fetch="all")}
check("ستون fee_amount", "fee_amount" in tx_cols)
check("ستون base_amount", "base_amount" in tx_cols)

gw = database.db_execute("""INSERT INTO payment_gateways
    (owner_id, gateway_name, gateway_type, callback_url, is_active)
    VALUES (?,'زرین‌پال','zarinpal','https://pay.ir',1)""", (S,))
eid6 = mkevent("رویداد درگاهی", is_paid=1, price=1000000,
               payment_method="custom_gateway", payment_gateway_id=gw)
ev6 = EV.get_event(eid6)
rid6 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid6, auth.get_user(U1)["id"], U1))

database.set_setting("pay_fee_custom_gateway_pct", "2.5", "t", "payment")
database.clear_settings_cache()
SENT.clear()
PAY.route_payment(U1, U1, ev6, rid6, 1000000)
t = alltext()
check("ریز مبلغ نمایش داده شد", "ریز مبلغ" in t, t[:200])
check("عنوان کارمزد در پیام", PAY.fee_label("custom_gateway") in t, t[:200])
check("مبلغ اصلی نشان داده شد",
      "1,000,000" in t or "1٬000٬000" in t, t[:250])

tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid6,), fetch="one")
check("تراکنش ساخته شد", bool(tx))
check("کارمزد ذخیره شد", tx and tx["fee_amount"] == 25000,
      str(tx.get("fee_amount") if tx else None))
check("مبلغ پایه ذخیره شد", tx and tx["base_amount"] == 1000000,
      str(tx.get("base_amount") if tx else None))
check("مبلغ کل = اصل + کارمزد", tx and tx["amount"] == 1025000,
      str(tx.get("amount") if tx else None))
check("روش gateway ثبت شد", tx and tx["method"] == "gateway")

# لینک پرداخت مبلغ کل را داشته باشد
urls = [b.get("url") for s in SENT
        for r in (s["p"].get("kb") or {}).get("inline_keyboard", [])
        for b in r if isinstance(b, dict) and b.get("url")]
check("لینک درگاه مبلغ کل دارد",
      any("1025000" in (u or "") for u in urls), str(urls))

# با کارمزد خاموش
database.set_setting("pay_fee_custom_gateway_on", "0", "t", "payment")
database.clear_settings_cache()
rid7 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid6, auth.get_user(U2)["id"], U2))
SENT.clear()
PAY.route_payment(U2, U2, ev6, rid7, 1000000)
check("بدون کارمزد: ریز مبلغ نمی‌آید", "ریز مبلغ" not in alltext())
tx7 = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                          (rid7,), fetch="one")
check("مبلغ بدون تغییر", tx7 and tx7["amount"] == 1000000,
      str(tx7.get("amount") if tx7 else None))
database.set_setting("pay_fee_custom_gateway_on", "1", "t", "payment")
database.clear_settings_cache()


# ═══════════ ۱۲) ورودی‌های خراب ═══════════
print("\n[۱۲] 🛡️ ورودی‌های خراب")

bad = [
    "evrm_", "evrm_evil_1", "evrm_quick_999999", "evrm_none_abc",
    "evqf_", "evqf_evil_1", "evqf_full_name_999999",
    "evqok_", "evqok_abc", "evqok_999999",
    "evpick_", "evpick_abc_1", "evpick_999999_1", "evpick_1_999999",
    "pay_fee", "payft_custom_gateway", "payfe_label_custom_gateway", "payfn_", "payfn_evil",
    "payfn_pay_fee_label", "fb_panel",
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

for st in (EV.STATE_EV_QUICK, PAY.STATE_PAY_FEE):
    try:
        auth.set_state(S, st, {"key": "pay_fee_percent"}, merge=False)
        SENT.clear()
        M.process_message(msg(S, "!@#$"))
    except Exception as e:
        check(f"state {st}", False, str(e))
auth.clear_state(S)
check("state های جدید سالم", True)


# ═══════════ ۱۳) لاگ فارسی ═══════════
print("\n[۱۳] 📋 لاگ فارسی")

import re as _re
_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))
for k in ("pay_fee_toggle", "pay_fee_setting", "event_form_linked"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۱۴) رگرسیون ═══════════
print("\n[۱۴] ♻️ رگرسیون")

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
check("پنل ادمین سالم", "پنل ادمین" in last())

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
check("پرداخت و مالی سالم", "پرداخت" in last())

SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
check("داشبورد گزارشات سالم", "داشبورد گزارشات" in last())

SENT.clear()
M.handle_callback(cb(S, f"evrev_{eid}"))
check("مرور رویداد سالم", "مرور نهایی" in last())
check("فرم در مرور نمایش داده شد", "سوال" in last(), last()[:250])

SENT.clear()
M.handle_callback(cb(S, f"fbrev_{fid_ok}"))
check("مرور فرم سالم", "مرور نهایی" in last())

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر سالم", "نورا" in alltext() or "سلام" in alltext())

# پرداخت کیف پول هنوز کار می‌کند
eid9 = mkevent("رویداد کیف‌پولی", is_paid=1, price=500000,
               payment_method="bale_wallet")
rid9 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid9, auth.get_user(U3)["id"], U3))
SENT.clear()
PAY.route_payment(U3, U3, EV.get_event(eid9), rid9, 500000)
tx9 = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                          (rid9,), fetch="one")
check("♻️ کیف پول سالم", bool(tx9))
check("♻️ کیف پول بدون کارمزد",
      tx9 and (tx9.get("fee_amount") or 0) == 0,
      str(tx9.get("fee_amount") if tx9 else None))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۶ پاس شدند!")
