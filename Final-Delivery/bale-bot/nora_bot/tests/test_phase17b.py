"""
تست فاز ۱۷-ب — رفع باگ‌های گزارش‌شده + تکمیل نهایی

باگ‌های گزارش‌شده:
  ۱) فرمی که مستقیم در رویداد ساخته می‌شود فعال نمی‌شود
  ۲) با برداشتن «تکمیل پروفایل» باز هم پروفایل می‌خواهد
  ۳) پروفایل کاربران قابل تنظیم نیست
  ۴) اطلاع‌رسانی به همه استارت‌زده‌ها نمی‌رود

تکمیل شده:
  🔗 وبهوک و رخدادها · 🔀 گردش کار (صف تأیید)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora17b_")
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
import form_reports as FR  # noqa: E402
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
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, FR, PAY, EV, AT, OC, AL, CL, TK, LT, PL, AD, M):
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
A1 = 1010001
U1, U2, U3, U4 = 1020001, 1020002, 1020003, 1020004

print("=" * 62)
print("🧪 تست فاز ۱۷-ب — رفع باگ + تکمیل نهایی")
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
PL.init_paylink_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
auth.create_auth_user({"id": A1, "first_name": "رضا"}, "09131111111", "phone")
PM.set_role(A1, "full_admin", S)

# U1, U2 احراز شده — U3 فقط استارت زده — U4 مسدود
for u, n in ((U1, "علی"), (U2, "سارا")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0913{u}", "phone")
database.db_execute("""INSERT INTO users
    (bale_user_id, first_name, is_authenticated, profile_status)
    VALUES (?,?,0,'draft')""", (U3, "محمد"))
database.db_execute("""INSERT INTO users
    (bale_user_id, first_name, is_authenticated, is_blocked)
    VALUES (?,?,1,1)""", (U4, "مسدود"))


# ═══════════ باگ ۱: فرم رویداد باید فعال باشد ═══════════
print("\n[۱] 🐛 فرم ساخته‌شده در رویداد فعال است")

eid = mkevent("کارگاه اول")
SENT.clear()
EV.create_reg_form(S, S, eid, advanced=True)
ev = EV.get_event(eid)
fid = ev.get("registration_form_id")
check("فرم ساخته و وصل شد", bool(fid))
frm = F.get_form(fid)
check("🐛 فرم فعال است (نه پیش‌نویس)",
      frm.get("status") == "active", str(frm.get("status")))
check("🔗 اتصال دوطرفه", frm.get("event_id") == eid)
nf = database.db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                        (fid,))
check("سوالات آماده اضافه شد", nf > 0, str(nf))

# فرم سریع هم فعال باشد
eid_q = mkevent("کارگاه سریع")
auth.set_state(S, EV.STATE_EV_QUICK, {f"qf_{eid_q}": "full_name,mobile"},
               merge=False)
SENT.clear()
EV.build_quick_form(S, S, eid_q)
fq = F.get_form(EV.get_event(eid_q).get("registration_form_id"))
check("فرم سریع هم فعال است", fq and fq.get("status") == "active",
      str(fq.get("status") if fq else None))
auth.clear_state(S)


# ═══════════ باگ ۲: require_profile محترم است ═══════════
print("\n[۲] 🐛 برداشتن «تکمیل پروفایل» رعایت می‌شود")

eid2 = mkevent("رویداد بدون پروفایل", require_profile=0)
check("رویداد require_profile=0 دارد",
      int(EV.get_event(eid2).get("require_profile") or 0) == 0)

# U1 پروفایل ناقص دارد
database.db_execute("UPDATE users SET profile_status='draft' "
                    "WHERE bale_user_id=?", (U1,))
SENT.clear()
EV.register(U1, U1, eid2)
check("🐛 بدون پروفایل هم ثبت‌نام می‌شود",
      "یک قدم تا همراهی" not in alltext()
      and "نیاز به پروفایل" not in alltext(), alltext()[:100])
reg = database.db_execute("SELECT * FROM event_registrations "
                          "WHERE event_id=? AND bale_user_id=?",
                          (eid2, U1), fetch="one")
check("ثبت‌نام انجام شد", bool(reg))

# اگر روشن باشد، باید بخواهد
eid3 = mkevent("رویداد با پروفایل", require_profile=1)
SENT.clear()
EV.register(U1, U1, eid3)
# فاز۱۷-ج: متن مهربان‌تر شد → «یک قدم تا همراهی»
check("✅ با روشن بودن، پروفایل می‌خواهد",
      ("پروفایل" in alltext() and "تأیید" in alltext())
      or "یک قدم تا همراهی" in alltext(), alltext()[:150])

# «بدون فرم» نباید require_profile را زور کند
database.db_execute("UPDATE events SET require_profile=0 WHERE id=?",
                    (eid2,))
SENT.clear()
M.handle_callback(cb(S, f"evrm_none_{eid2}"))
check("🐛 «بدون فرم» require_profile را عوض نمی‌کند",
      int(EV.get_event(eid2).get("require_profile") or 0) == 0,
      str(EV.get_event(eid2).get("require_profile")))

# در مرور قابل تغییر است
SENT.clear()
M.handle_callback(cb(S, f"evrev_{eid2}"))
check("👤 پروفایل در مرور نمایش داده شد",
      "پروفایل" in last(), last()[:200])
check("دکمه تاگل پروفایل",
      f"evtogr_require_profile_{eid2}" in allcb(), str(allcb())[:120])
M.handle_callback(cb(S, f"evtogr_require_profile_{eid2}"))
check("تاگل از مرور کار می‌کند",
      int(EV.get_event(eid2).get("require_profile") or 0) == 1)


# ═══════════ باگ ۳: ویرایش پروفایل کاربر ═══════════
print("\n[۳] ✏️ ویرایش پروفایل کاربران توسط ادمین")

check("۱۹ فیلد قابل ویرایش (امتیاز جدا شد → دفترکل)", len(AD.PROFILE_EDIT_FIELDS) == 19,
      str(len(AD.PROFILE_EDIT_FIELDS)))
keys = [k for k, _, _ in AD.PROFILE_EDIT_FIELDS]
for k in ("first_name", "last_name", "mobile", "national_id", "birth_date",
          "gender", "city", "education_level", "email"):
    check(f"فیلد {k}", k in keys)
check("🔒 total_points در ویرایشگر پروفایل نیست", "total_points" not in keys)

u1row = auth.get_user(U1)
tid = u1row["id"]

SENT.clear()
M.handle_callback(cb(S, f"uv_{tid}"))
check("دکمه ویرایش در جزئیات کاربر",
      f"upe_{tid}" in allcb(), str(allcb())[:120])

SENT.clear()
M.handle_callback(cb(S, f"upe_{tid}"))
check("ویرایشگر باز شد", "ویرایش پروفایل" in last(), last()[:50])
ed = allcb()
check("همه فیلدها دکمه دارند",
      sum(1 for d in ed if d.startswith("upf_")) == 19, str(len(ed)))
check("دکمه تأیید پروفایل", f"upst_{tid}" in ed)
check("دکمه محاسبه درصد", f"uprc_{tid}" in ed)

# ویرایش متنی
SENT.clear()
M.handle_callback(cb(S, f"upf_city_{tid}"))
check("ویرایش شهر شروع شد", "شهر" in last(), last()[:40])
M.process_message(msg(S, "اصفهان"))
check("شهر ذخیره شد", auth.get_user(U1).get("city") == "اصفهان",
      str(auth.get_user(U1).get("city")))
check("به ویرایشگر برگشت", "ویرایش پروفایل" in last())

# فیلد انتخابی
SENT.clear()
M.handle_callback(cb(S, f"upf_gender_{tid}"))
check("انتخاب جنسیت", "جنسیت" in last(), last()[:40])
check("گزینه‌ها دکمه دارند",
      any(d.startswith("upv_gender_") for d in allcb()), str(allcb())[:100])
M.handle_callback(cb(S, f"upv_gender_0_{tid}"))
check("جنسیت ذخیره شد", auth.get_user(U1).get("gender") == "مرد",
      str(auth.get_user(U1).get("gender")))

# مقطع تحصیلی
M.handle_callback(cb(S, f"upv_education_level_3_{tid}"))
check("مقطع ذخیره شد",
      auth.get_user(U1).get("education_level") == "کارشناسی",
      str(auth.get_user(U1).get("education_level")))

# خالی کردن
M.handle_callback(cb(S, f"upv_gender_x_{tid}"))
check("خالی کردن کار می‌کند", not auth.get_user(U1).get("gender"))
M.handle_callback(cb(S, f"upv_gender_0_{tid}"))

# اعتبارسنجی موبایل
SENT.clear()
M.handle_callback(cb(S, f"upf_mobile_{tid}"))
M.process_message(msg(S, "123"))
check("🔒 موبایل نامعتبر رد شد", "معتبر" in last(), last()[:40])
M.process_message(msg(S, "09129998877"))
check("موبایل ذخیره شد",
      auth.get_user(U1).get("mobile") == "09129998877",
      str(auth.get_user(U1).get("mobile")))

# موبایل تکراری
SENT.clear()
M.handle_callback(cb(S, f"upf_mobile_{tid}"))
M.process_message(msg(S, "09120000000"))
check("🔒 موبایل تکراری رد شد", "دیگری" in last(), last()[:50])
auth.clear_state(S)

# تاریخ تولد
SENT.clear()
M.handle_callback(cb(S, f"upf_birth_date_{tid}"))
M.process_message(msg(S, "بد"))
check("🔒 تاریخ نامعتبر رد شد", "قالب" in last(), last()[:40])
M.process_message(msg(S, "1370/05/12"))
check("تاریخ ذخیره شد",
      auth.get_user(U1).get("birth_date") == "1370/05/12")

# کد ملی
SENT.clear()
M.handle_callback(cb(S, f"upf_national_id_{tid}"))
M.process_message(msg(S, "123"))
check("🔒 کد ملی کوتاه رد شد", "۱۰ رقم" in last(), last()[:40])
M.process_message(msg(S, "1234567890"))
check("کد ملی ذخیره شد",
      auth.get_user(U1).get("national_id") == "1234567890")

# ایمیل
SENT.clear()
M.handle_callback(cb(S, f"upf_email_{tid}"))
M.process_message(msg(S, "بدون-اتساین"))
check("🔒 ایمیل نامعتبر رد شد", "معتبر" in last(), last()[:40])
M.process_message(msg(S, "a@b.com"))
check("ایمیل ذخیره شد", auth.get_user(U1).get("email") == "a@b.com")

# امتیاز — دیگر از فرم ویرایش نیست؛ فقط «تعدیل امتیاز» سوپرادمین از دفترکل
SENT.clear()
M.handle_callback(cb(S, f"upf_total_points_{tid}"))
M.process_message(msg(S, "150"))
check("🔒 فرم ویرایش امتیاز را نمی‌نویسد",
      int(auth.get_user(U1).get("total_points") or 0) == 0,
      str(auth.get_user(U1).get("total_points")))
import admin as _AD_PTS
_AD_PTS.POINTS_MANUAL_ADJUST_MAX = 0
SENT.clear()
M.handle_callback(cb(S, f"upts_{tid}"))
check("⛔ بدون سقف محیطی، تعدیل غیرفعال (fail-closed)", "غیرفعال" in last(), last()[:60])
_AD_PTS.POINTS_MANUAL_ADJUST_MAX = 500
SENT.clear()
M.handle_callback(cb(S, f"upts_{tid}"))
M.process_message(msg(S, "+150"))
M.process_message(msg(S, "تست تعدیل دستی با دلیل"))
check("هنوز تأیید نشده → بدون تغییر",
      int(auth.get_user(U1).get("total_points") or 0) == 0)
M.handle_callback(cb(S, f"uptsok_{tid}"))
check("امتیاز با تعدیل دفترکل ثبت شد",
      int(auth.get_user(U1).get("total_points") or 0) == 150,
      str(auth.get_user(U1).get("total_points")))
M.handle_callback(cb(S, f"uptsok_{tid}"))
check("تأیید دوباره بی‌اثر است",
      int(auth.get_user(U1).get("total_points") or 0) == 150)
check("ردیف دفترکل با دلیل و عامل", database.db_execute(
    "SELECT COUNT(*) AS c FROM points_ledger WHERE entry_type='manual_adjust' "
    "AND actor_id=? AND reason LIKE '%دلیل%'", (S,), fetch="one")["c"] == 1)

# درصد تکمیل
SENT.clear()
M.handle_callback(cb(S, f"uprc_{tid}"))
check("درصد محاسبه شد", "درصد" in alltext(), alltext()[:60])
check("درصد بیشتر از صفر",
      int(auth.get_user(U1).get("complete_profile_percent") or 0) > 0,
      str(auth.get_user(U1).get("complete_profile_percent")))

# تأیید پروفایل
SENT.clear()
M.handle_callback(cb(S, f"upst_{tid}"))
check("پروفایل تأیید شد",
      auth.get_user(U1).get("profile_status") == "approved")
check("به کاربر خبر رفت",
      any("تأیید" in t for t in to(U1)), str(to(U1))[-80:])
M.handle_callback(cb(S, f"upst_{tid}"))
check("لغو تأیید کار می‌کند",
      auth.get_user(U1).get("profile_status") == "draft")

# 🔒 سوپرادمین محافظت‌شده
srow = auth.get_user(S)
SENT.clear()
M.handle_callback(cb(A1, f"upe_{srow['id']}"))
check("🔒 ادمین دیگر پروفایل سوپرادمین را ویرایش نمی‌کند",
      "سوپرادمین" in last() or "دسترسی" in last(), last()[:50])

# 🔒 کاربر عادی
SENT.clear()
M.handle_callback(cb(U2, f"upe_{tid}"))
check("🔒 کاربر عادی دسترسی ندارد", "دسترسی" in last())
SENT.clear()
M.handle_callback(cb(U2, f"upf_city_{tid}"))
check("🔒 کاربر عادی ویرایش نمی‌کند", "دسترسی" in last())


# ═══════════ باگ ۴: اطلاع‌رسانی به همه ═══════════
print("\n[۴] 📢 اطلاع‌رسانی به همه استارت‌زده‌ها")

check("فیلتر everyone وجود دارد", "everyone" in AD.BC_FILTERS)

n_all = AD.bc_count("all")
n_every = AD.bc_count("everyone")
check("«همه کاربران» فقط احراز شده‌ها", n_all >= 3, str(n_all))
check("U3 بدون احراز در all نیست",
      not any(t["bale_user_id"] == U3 for t in AD.bc_targets("all")))
check("🐛 «هرکس استارت زده» بیشتر است", n_every > n_all,
      f"{n_every} > {n_all}")
check("U3 (بدون احراز) در everyone هست",
      any(t["bale_user_id"] == U3 for t in AD.bc_targets("everyone")))
check("U3 در all نیست",
      not any(t["bale_user_id"] == U3 for t in AD.bc_targets("all")))
check("🔒 مسدود در هیچ‌کدام نیست",
      not any(t["bale_user_id"] == U4 for t in AD.bc_targets("everyone")))

SENT.clear()
M.handle_callback(cb(S, "admin_broadcast"))
check("دکمه everyone در منو", "bcf_everyone" in allcb(), str(allcb())[:150])

# ارسال واقعی
SENT.clear()
M.handle_callback(cb(S, "bcf_everyone"))
M.process_message(msg(S, "سلام به همه"))
check("متن دریافت شد", "پیش‌نمایش" in last() or "ارسال" in last(),
      last()[:60])
SENT.clear()
M.handle_callback(cb(S, "bc_go"))
got_u3 = any("سلام به همه" in t for t in to(U3))
check("🐛 پیام به کاربر بدون احراز رسید", got_u3, str(to(U3))[:80])
check("🔒 به مسدود نرفت",
      not any("سلام به همه" in t for t in to(U4)))


# ═══════════ ۵) 🔗 وبهوک ═══════════
print("\n[۵] 🔗 وبهوک و رخدادها")

cols = {c["name"] for c in
        database.db_execute("PRAGMA table_info(forms)", fetch="all")}
for c in ("webhook_url", "webhook_events", "workflow_enabled",
          "workflow_steps"):
    check(f"ستون {c}", c in cols)

check("تابع _fire_webhook", hasattr(FF, "_fire_webhook"))
check("بدون URL کاری نمی‌کند",
      not FF._fire_webhook({"webhook_url": ""}, {}, "completed"))
check("🔒 URL غیر HTTPS رد می‌شود",
      not FF._fire_webhook({"webhook_url": "http://x.com"}, {}, "completed"))
check("رویداد نامرتبط رد می‌شود",
      not FF._fire_webhook({"webhook_url": "https://x.com",
                            "webhook_events": "paid"}, {}, "completed"))
check("رویداد درست پذیرفته می‌شود",
      FF._fire_webhook({"webhook_url": "https://x.invalid",
                        "webhook_events": "completed",
                        "id": 1, "title": "t"}, {"id": 1}, "completed"))

fid_w = database.db_execute(
    "INSERT INTO forms (owner_id, form_type, title, slug, status) "
    "VALUES (?,'questionnaire','فرم وبهوک','wh1','active')", (S,))
SENT.clear()
# 🔄 فاز ۴۰: وبهوک و گردش کار به لایهٔ دوم «⋮ بیشتر» رفتند
F.show_advanced2(S, S, fid_w)
adv = allcb()
check("🔗 دکمه وبهوک در تنظیمات",
      f"fbset_webhook_url_{fid_w}" in adv, str(adv)[:150])
check("🔀 دکمه گردش کار",
      f"fbtog_workflow_enabled_{fid_w}" in adv)

SENT.clear()
M.handle_callback(cb(S, f"fbset_webhook_url_{fid_w}"))
check("ویرایش وبهوک", "وبهوک" in last(), last()[:40])
M.process_message(msg(S, "https://example.com/hook"))
check("آدرس ذخیره شد",
      F.get_form(fid_w).get("webhook_url") == "https://example.com/hook")


# ═══════════ ۶) 🔀 گردش کار ═══════════
print("\n[۶] 🔀 گردش کار — صف تأیید")

fid_a = database.db_execute(
    "INSERT INTO forms (owner_id, form_type, title, slug, status, "
    "needs_approval) VALUES (?,'registration','فرم تأییدی','ap1','active',1)",
    (S,))
database.db_execute("INSERT INTO form_fields (form_id, field_order, "
                    "field_type, label) VALUES (?,1,'short_text','نام')",
                    (fid_a,))
rid_a = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, tracking_code)
    VALUES (?,?,'pending_review','TRK5')""", (fid_a, U2))

SENT.clear()
M.handle_callback(cb(S, "fb_approvals"))
check("صف تأیید باز شد", "صف تأیید" in last(), last()[:50])
check("پاسخ در صف هست", f"fwok_{rid_a}" in allcb(), str(allcb())[:120])

SENT.clear()
M.handle_callback(cb(S, "fb_panel"))
check("🔴 badge صف در پنل", "صف تأیید" in last() or "fb_approvals" in
      str(allcb()), str(allcb())[:150])

# تأیید
SENT.clear()
M.handle_callback(cb(S, f"fwok_{rid_a}"))
st = database.db_execute("SELECT status FROM form_responses WHERE id=?",
                         (rid_a,), fetch="one")["status"]
check("پاسخ تأیید شد", st == "completed", st)
check("به کاربر خبر رفت",
      any("تأیید شد" in t for t in to(U2)), str(to(U2))[-80:])

# دوباره
SENT.clear()
M.handle_callback(cb(S, f"fwok_{rid_a}"))
check("🔒 بررسی دوباره جلوگیری شد", "قبلاً" in last(), last()[:40])

# رد
rid_b = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'pending_review')""",
    (fid_a, U1))
SENT.clear()
M.handle_callback(cb(S, f"fwno_{rid_b}"))
check("پاسخ رد شد",
      database.db_execute("SELECT status FROM form_responses WHERE id=?",
                          (rid_b,), fetch="one")["status"] == "rejected")
check("پیام رد به کاربر",
      any("تأیید نشد" in t for t in to(U1)), str(to(U1))[-80:])

# تأیید فرم متصل به رویداد → ثبت‌نام
eid_w = mkevent("رویداد گردش کار", require_profile=0)
fid_ev = database.db_execute(
    "INSERT INTO forms (owner_id, form_type, title, slug, status, "
    "needs_approval, event_id) "
    "VALUES (?,'registration','فرم رویدادی','ap2','active',1,?)", (S, eid_w))
database.db_execute("UPDATE events SET registration_form_id=? WHERE id=?",
                    (fid_ev, eid_w))
rid_c = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'pending_review')""",
    (fid_ev, U2))
SENT.clear()
M.handle_callback(cb(S, f"fwok_{rid_c}"))
reg_w = database.db_execute("SELECT * FROM event_registrations "
                            "WHERE event_id=? AND bale_user_id=?",
                            (eid_w, U2), fetch="one")
check("🔗 تأیید → ثبت‌نام رویداد انجام شد", bool(reg_w))

# 🔒 دسترسی
SENT.clear()
M.handle_callback(cb(U1, "fb_approvals"))
check("🔒 کاربر عادی صف را نمی‌بیند", "دسترسی" in last())


# ═══════════ ۷) ورودی‌های خراب ═══════════
print("\n[۷] 🛡️ ورودی‌های خراب")

bad = [
    "upe_", "upe_abc", "upe_999999",
    "upf_", "upf_evil_1", "upf_city_999999", "upf_is_admin_1",
    "upv_", "upv_gender_x", "upv_evil_0_1", "upv_gender_99_1",
    "upst_abc", "upst_999999", "uprc_abc",
    "fb_approvals", "fwok_", "fwok_abc", "fwok_999999", "fwno_abc",
    "bcf_everyone", "bcf_evil",
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
auth.clear_state(S)

try:
    auth.set_state(S, AD.STATE_EDIT_PROFILE, {"tid": 999999, "key": "city"},
                   merge=False)
    SENT.clear()
    M.process_message(msg(S, "تست"))
    check("state با کاربر ناموجود امن", True)
except Exception as e:
    check("state با کاربر ناموجود امن", False, str(e))
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
for k in ("admin_edit_profile", "form_reviewed"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۹) رگرسیون ═══════════
print("\n[۹] ♻️ رگرسیون")

for d, expect in (("admin_panel", "پنل ادمین"),
                  ("admin_users", "مدیریت کاربران"),
                  ("set_payment", "پرداخت"),
                  ("admin_stats", "داشبورد گزارشات"),
                  ("fb_panel", "فرم‌ساز"),
                  ("pl_panel", "غیرمتمرکز"),
                  ("pay_fee", "کارمزد"),
                  ("lt_all", "قرعه‌کشی")):
    SENT.clear()
    M.handle_callback(cb(S, d))
    check(f"{expect} سالم", expect in last(), last()[:45])

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر سالم", "نورا" in alltext() or "سلام" in alltext())
SENT.clear()
M.process_message(msg(S, "/start"))
check("start ادمین سالم", "نورا" in alltext() or "سلام" in alltext())

# پرداخت سالم
eid_p = mkevent("رویداد پولی", is_paid=1, price=500000,
                payment_method="bale_wallet", require_profile=0)
rid_p = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid_p, auth.get_user(U1)["id"], U1))
SENT.clear()
PAY.route_payment(U1, U1, EV.get_event(eid_p), rid_p, 500000)
check("♻️ پرداخت سالم",
      bool(database.db_execute("SELECT * FROM transactions "
                               "WHERE registration_id=?", (rid_p,),
                               fetch="one")))

# جریان کامل: ثبت‌نام با فرم
eid_f = mkevent("رویداد فرم‌دار", require_profile=0)
auth.set_state(S, EV.STATE_EV_QUICK, {f"qf_{eid_f}": "full_name,mobile"},
               merge=False)
EV.build_quick_form(S, S, eid_f)
auth.clear_state(S)
SENT.clear()
EV.register(U2, U2, eid_f)
check("🔗 فرم به کاربر نشان داده شد",
      "تکمیل فرم" in alltext(), alltext()[:80])
auth.clear_state(U2)


# ═══════════ ۱۰) یکپارچگی ═══════════
print("\n[۱۰] 🧩 یکپارچگی")

check("هیچ فرم رویدادی پیش‌نویس نمانده",
      (database.db_scalar("""SELECT COUNT(*) FROM forms
          WHERE event_id IS NOT NULL AND status='draft'""") or 0) == 0)
check("اتصال دوطرفه سالم",
      (database.db_scalar("""SELECT COUNT(*) FROM events e
          WHERE e.registration_form_id IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM forms f
                            WHERE f.id=e.registration_form_id
                              AND f.event_id=e.id)""") or 0) == 0)
check("امتیاز منفی نیست",
      (database.db_scalar("SELECT COUNT(*) FROM users "
                          "WHERE total_points < 0") or 0) == 0)
check("درصد پروفایل معتبر",
      (database.db_scalar("""SELECT COUNT(*) FROM users
          WHERE complete_profile_percent < 0
             OR complete_profile_percent > 100""") or 0) == 0)


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۷-ب پاس شدند!")
