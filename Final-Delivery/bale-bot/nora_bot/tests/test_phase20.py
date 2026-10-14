"""
تست فاز ۲۰ — 📣 تبلیغات · 🎛️ چیدمان کاربر · 🎫 بلیط جامع

درخواست کاربر:
  ۱) «قسمت پشتیبانی و درباره ما مشکل داره، نمای کاربر خیلی پخش و پلاس،
      ادمین بتونه هر بخشی دوست داشت خاموش و روشن کنه»
  ۲) «بخش مدیریت قالب و بلیط‌ها خیلی بهم‌ریختس، کامل و جامع کن»
  ۳) «قسمت تبلیغات در اطلاع‌رسانی اضافه کن، خیلی شیک و جامع»
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora20_")
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
    SENT.append({"m": "sendMessage", "p": {"cid": cid, "text": text,
                                           "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption,
                                    "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file("sendPhoto", "p", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file("sendDocument", "d", c, d, cap, kb)
bale_api.send_invoice = lambda c, **kw: {"ok": True, "result": {"message_id": 1}}

import config  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import ads as AD  # noqa: E402
import about as AB  # noqa: E402
import certgen as CG  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import forms as F  # noqa: E402
import payments as PAY  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import admin as ADM  # noqa: E402
import settings_admin as SET  # noqa: E402
import main as M  # noqa: E402

for mod in (AD, AB, CG, EV, AT, F, PAY, OC, CL, TK, ADM, SET, M):
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
    """تعداد دکمه‌های آخرین پیام"""
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


S = 100000001
U1, U2 = 1660001, 1660002

print("=" * 62)
print("🧪 تست فاز ۲۰ — تبلیغات · چیدمان · بلیط")
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
TK.init_inbox_table()
AB.init_about_tables()
CG.init_cert_tables()
AD.init_ads_tables()
database.seed_default_settings()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, n in ((U1, "سارا"), (U2, "علی")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0918{u}", "phone")
    database.db_execute("UPDATE users SET profile_status='approved', "
                        "complete_profile_percent=100 WHERE bale_user_id=?",
                        (u,))
for i in range(8):
    auth.create_auth_user({"id": 1700000 + i, "first_name": f"u{i}"},
                          f"09190000{i:03d}", "phone")


# ═══════════ ۱) 🎛️ چیدمان نمای کاربر ═══════════
print("\n[۱] 🎛️ چیدمان نمای کاربر")

check("۳ چیدمان تعریف شده", len(AB.LAYOUTS) == 3, str(list(AB.LAYOUTS)))
check("پیش‌فرض «گروهی» است", AB.layout() == "grouped", AB.layout())

database.db_execute("""INSERT INTO about_links
    (kind, title, url, is_active) VALUES ('bale_channel','کانال','x',1)""")
database.db_execute("""INSERT INTO about_people
    (name, role, is_active) VALUES ('علی','مدیر',1)""")

counts = {}
for lay in ("compact", "grouped", "full"):
    database.set_setting("ab_layout", lay, "t", "about")
    database.clear_settings_cache()
    SENT.clear()
    M.handle_callback(cb(U1, "u_support"))
    counts[lay] = nbtn()
    check(f"چیدمان «{lay}» کار می‌کند", nbtn() > 0, str(nbtn()))

check("🔴 خلاصه کمترین دکمه را دارد",
      counts["compact"] < counts["full"], str(counts))
check("🔴 گروهی بین آن دو است",
      counts["compact"] <= counts["grouped"] <= counts["full"],
      str(counts))
check("🔴 خلاصه واقعاً کم است (≤۵)", counts["compact"] <= 5,
      str(counts["compact"]))

# پنل ادمین چیدمان
SENT.clear()
M.handle_callback(cb(S, "ab_layout"))
check("پنل چیدمان باز شد", "چیدمان" in last(), last()[:50])
check("هر ۳ گزینه دکمه دارند",
      sum(1 for c in allcb() if c.startswith("ablay_")) == 3)
M.handle_callback(cb(S, "ablay_compact"))
database.clear_settings_cache()
check("✅ تغییر چیدمان ذخیره شد", AB.layout() == "compact", AB.layout())
M.handle_callback(cb(S, "ablay_grouped"))
database.clear_settings_cache()

# چیدمان نامعتبر
database.set_setting("ab_layout", "چرت", "t", "about")
database.clear_settings_cache()
check("🔒 چیدمان نامعتبر → پیش‌فرض", AB.layout() == "grouped")
database.set_setting("ab_layout", "grouped", "t", "about")
database.clear_settings_cache()


print("\n[۱.۲] ⚡ روشن/خاموش گروهی بخش‌ها")

SENT.clear()
M.handle_callback(cb(S, "ab_bulk"))
check("پنل گروهی باز شد", "روشن" in last(), last()[:50])

M.handle_callback(cb(S, "abbulk_off"))
database.clear_settings_cache()
check("⚪ همه بخش‌ها خاموش شد",
      not AB.block_on("intro") and not AB.block_on("ticket"))
SENT.clear()
M.handle_callback(cb(U1, "u_support"))
check("🔴 با خاموش بودن همه، صفحه کرش نمی‌کند",
      "پشتیبانی" in last(), last()[:50])

M.handle_callback(cb(S, "abbulk_on"))
database.clear_settings_cache()
check("🟢 همه روشن شد",
      AB.block_on("intro") and AB.block_on("ticket"))

M.handle_callback(cb(S, "abbulk_reset"))
database.clear_settings_cache()
check("♻️ بازگشت به پیش‌فرض",
      AB.block_on("intro") and not AB.block_on("achieve"))

# تک‌تک هم کار کند
M.handle_callback(cb(S, "abt_team"))
database.clear_settings_cache()
check("تک‌تک هم خاموش می‌شود", not AB.block_on("team"))
M.handle_callback(cb(S, "abt_team"))
database.clear_settings_cache()


# ═══════════ ۲) 🎓 هاب گواهینامه و بلیط ═══════════
print("\n[۲] 🎓 هاب گواهینامه و بلیط")

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("هاب باز شد", "گواهینامه و بلیط" in last(), last()[:60])
_c = allcb()
for want in ("ct_panel", "ct_assets", "ct_set_cert", "ct_set_ticket",
             "ct_stats", "ct_install"):
    check(f"دکمه {want} در هاب هست", want in _c)
check("وضعیت آمادگی نمایش داده می‌شود",
      "قالب فعال" in last(), last()[:200])

SENT.clear()
M.handle_callback(cb(S, "ct_stats"))
check("📊 صفحه آمار باز شد", "آمار گواهینامه" in last(), last()[:50])
check("وضعیت پاکسازی نمایش داده می‌شود",
      "پاکسازی" in last(), last()[:300])


print("\n[۲.۲] 🎫 بلیط جامع")

check("🔴 تنظیمات بلیط گسترش یافت",
      len(CG.TICKET_SETTINGS) >= 20, str(len(CG.TICKET_SETTINGS)))
_keys = {r[0] for r in CG.TICKET_SETTINGS}
for k in ("tk_title", "tk_show_name", "tk_show_nid", "tk_show_seat",
          "tk_qr_on", "tk_verify_on", "tk_once_only", "tk_style",
          "tk_rules_text", "tk_footer", "tk_image_on"):
    check(f"تنظیم {k} هست", k in _keys)

check("تابع ساخت متن بلیط هست", hasattr(CG, "build_ticket_text"))

_reg = {"ticket_code": "TK-123", "amount_paid": 500000,
        "start_date": "1405/06/15", "start_time": "18:30",
        "location_address": "سالن اصلی", "organizer": "واحد آموزش",
        "title": "همایش بزرگ"}
_u = {"first_name": "سارا", "last_name": "محمدی",
      "mobile": "09121234567", "national_id": "0012345678"}

_t = CG.build_ticket_text(_reg, _u, _reg)
check("🎫 متن بلیط ساخته شد", len(_t) > 50)
check("🎫 نام در بلیط هست", "سارا" in _t)
check("🎫 کد بلیط هست", "TK-123" in _t)
check("🎫 تاریخ هست", "1405/06/15" in _t)
check("🎫 مکان هست", "سالن اصلی" in _t)
check("🔒 کد ملی پیش‌فرض نمایش داده نمی‌شود",
      "0012345678" not in _t, _t[:200])

# خاموش کردن بخش‌ها
database.set_setting("tk_show_mobile", "0", "t", "certificate")
database.set_setting("tk_show_price", "0", "t", "certificate")
database.clear_settings_cache()
_t2 = CG.build_ticket_text(_reg, _u, _reg)
check("🔴 موبایل خاموش شد", "09121234567" not in _t2)
check("🔴 مبلغ خاموش شد", "500,000" not in _t2 and "500٬000" not in _t2)
check("🟢 ولی نام هنوز هست", "سارا" in _t2)

# روشن کردن کد ملی
database.set_setting("tk_show_nid", "1", "t", "certificate")
database.clear_settings_cache()
check("🟢 کد ملی روشن شد",
      "0012345678" in CG.build_ticket_text(_reg, _u, _reg))

# عنوان و پانویس دلخواه
database.set_setting("tk_title", "کارت ورود", "t", "certificate")
database.set_setting("tk_footer", "گروه خط زندگی", "t", "certificate")
database.clear_settings_cache()
_t3 = CG.build_ticket_text(_reg, _u, _reg)
check("🏷️ عنوان دلخواه اعمال شد", "کارت ورود" in _t3, _t3[:60])
check("🏷️ پانویس اعمال شد", "گروه خط زندگی" in _t3)

# قوانین
database.set_setting("tk_show_rules", "1", "t", "certificate")
database.set_setting("tk_rules_text", "۳۰ دقیقه زودتر بیایید",
                     "t", "certificate")
database.clear_settings_cache()
check("📜 قوانین ورود اعمال شد",
      "۳۰ دقیقه زودتر" in CG.build_ticket_text(_reg, _u, _reg))

check("🛡️ ورودی خالی کرش نمی‌کند",
      isinstance(CG.build_ticket_text(None, None, None), str))

# بلیط واقعی رویداد
_eid = database.db_execute("""INSERT INTO events
    (title, event_type, status, capacity, created_by, has_ticket,
     start_date, start_time)
    VALUES ('همایش تستی','workshop','published',50,?,1,
            '1405/06/15','18:30')""", (S,))
database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status, ticket_code)
    VALUES (?,?,?,'confirmed','TK-9911')""",
    (_eid, auth.get_user(U1)["id"], U1))
SENT.clear()
EV.show_ticket(U1, U1, _eid)
check("🔴 بلیط واقعی از تنظیمات ساخته می‌شود",
      "کارت ورود" in alltext(), alltext()[:150])
check("🔴 کد بلیط واقعی نمایش داده شد", "TK-9911" in alltext())

# برگرداندن پیش‌فرض‌ها
for k in ("tk_show_mobile", "tk_show_price", "tk_show_rules"):
    database.set_setting(k, "1" if k != "tk_show_rules" else "0",
                         "t", "certificate")
database.set_setting("tk_title", "بلیت ورود", "t", "certificate")
database.set_setting("tk_show_nid", "0", "t", "certificate")
database.clear_settings_cache()


# ═══════════ ۳) 📣 پنل تبلیغات ═══════════
print("\n[۳] 📣 پنل تبلیغات")

check("انواع کمپین تعریف شده", len(AD.AD_TYPES) >= 6,
      str(len(AD.AD_TYPES)))
check("زمان‌بندی‌ها تعریف شده", len(AD.SCHEDULES) >= 4)
check("وضعیت‌ها تعریف شده", len(AD.AD_STATUS) >= 5)
check("تنظیمات تعریف شده", len(AD.AD_SETTINGS) >= 5)

SENT.clear()
M.handle_callback(cb(S, "ad_panel"))
check("پنل تبلیغات باز شد", "پنل تبلیغات" in last(), last()[:50])
_c = allcb()
for want in ("ad_new", "ad_report", "ad_settings", "ad_tips"):
    check(f"دکمه {want} هست", want in _c)

SENT.clear()
M.handle_callback(cb(S, "ad_new"))
check("انتخاب نوع کمپین", "نوع" in last(), last()[:50])
check("همه انواع دکمه دارند",
      sum(1 for c in allcb() if c.startswith("adnew_"))
      == len(AD.AD_TYPES))

# ساخت کمپین
SENT.clear()
M.handle_callback(cb(S, "adnew_promo"))
check("ویزارد شروع شد", auth.get_state_name(S) == AD.STATE_AD_NEW)
M.process_message(msg(S, "کمپین تست"))
check("نام گرفته شد", "متن پیام" in last(), last()[:50])
M.process_message(msg(S, "سلام {نام}! دوره جدید ما شروع شد 🎉"))
_ad = database.db_execute("SELECT * FROM ad_campaigns ORDER BY id DESC "
                          "LIMIT 1", fetch="one")
check("✅ کمپین ساخته شد", bool(_ad) and _ad["title"] == "کمپین تست")
check("متن ذخیره شد", "دوره جدید" in (_ad["body"] or ""))
check("وضعیت پیش‌نویس", _ad["status"] == "draft")
_aid = _ad["id"]

# شخصی‌سازی متن
_body = AD._render_body(_ad, {"first_name": "سارا",
                              "last_name": "محمدی"})
check("🔴 {نام} با نام واقعی جایگزین شد",
      "سارا محمدی" in _body, _body[:80])
check("🔴 آکولاد خام نماند", "{نام}" not in _body)
_anon = AD._render_body(_ad, None)
check("بدون کاربر هم متن سالم است", "دوست عزیز" in _anon, _anon[:60])

# مخاطب
SENT.clear()
M.handle_callback(cb(S, f"adtgt_{_aid}"))
check("🎯 صفحه مخاطب باز شد", "مخاطب" in last(), last()[:50])
check("تعداد نفرات هر فیلتر نمایش داده می‌شود",
      "نفر" in last(), last()[:200])
M.handle_callback(cb(S, f"adtg_approved_{_aid}"))
check("مخاطب ذخیره شد",
      AD.get_ad(_aid)["target"] == "approved",
      AD.get_ad(_aid)["target"])

# دکمه اقدام
SENT.clear()
M.handle_callback(cb(S, f"adbtn_{_aid}"))
check("🔘 صفحه دکمه باز شد", "دکمه" in last(), last()[:50])
M.handle_callback(cb(S, f"ade_btn_text_{_aid}"))
M.process_message(msg(S, "ثبت‌نام کن"))
check("متن دکمه ذخیره شد",
      AD.get_ad(_aid)["btn_text"] == "ثبت‌نام کن")

# لینک نامعتبر رد شود
M.handle_callback(cb(S, f"ade_btn_url_{_aid}"))
SENT.clear()
M.process_message(msg(S, "بدون http"))
check("🔒 لینک نامعتبر رد شد", "http" in last(), last()[:50])
M.process_message(msg(S, "https://ble.ir/test"))
check("✅ لینک درست ذخیره شد",
      AD.get_ad(_aid)["btn_url"] == "https://ble.ir/test")

# A/B تست
SENT.clear()
M.handle_callback(cb(S, f"adab_{_aid}"))
check("🅱️ صفحه A/B باز شد", "A/B" in last() or "🅱️" in last(),
      last()[:50])
M.handle_callback(cb(S, f"ade_body_b_{_aid}"))
M.process_message(msg(S, "نسخه دوم — تخفیف ویژه!"))
check("🅱️ نسخه دوم ذخیره شد",
      "تخفیف ویژه" in (AD.get_ad(_aid)["body_b"] or ""))
check("🅱️ A/B خودکار فعال شد", AD.get_ad(_aid)["ab_test"] == 1)
_bb = AD._render_body(AD.get_ad(_aid), None, "b")
check("🅱️ نسخه دوم رندر می‌شود", "تخفیف ویژه" in _bb)

# زمان‌بندی
SENT.clear()
M.handle_callback(cb(S, f"adsch_{_aid}"))
check("⏰ صفحه زمان‌بندی باز شد", "زمان" in last(), last()[:50])
M.handle_callback(cb(S, f"adsc_at_{_aid}"))
M.process_message(msg(S, "1405/07/01 10:30"))
_a2 = AD.get_ad(_aid)
check("📅 تاریخ ذخیره شد", _a2["run_at"] == "1405/07/01",
      str(_a2["run_at"]))
check("🕐 ساعت ذخیره شد", _a2["run_time"] == "10:30",
      str(_a2["run_time"]))
check("وضعیت زمان‌بندی‌شده شد", _a2["status"] == "scheduled")

# ساعت نامعتبر
M.handle_callback(cb(S, f"adsc_at_{_aid}"))
SENT.clear()
M.process_message(msg(S, "1405/07/01 99:99"))
check("🔒 ساعت نامعتبر رد شد", "نامعتبر" in last(), last()[:50])
auth.clear_state(S)

# پیشرفته
SENT.clear()
M.handle_callback(cb(S, f"adadv_{_aid}"))
check("⚡ صفحه پیشرفته باز شد", "سرعت" in last(), last()[:50])
M.handle_callback(cb(S, f"ade_rate_{_aid}"))
M.process_message(msg(S, "15"))
check("🐢 سرعت ذخیره شد", AD.get_ad(_aid)["rate"] == 15)
M.handle_callback(cb(S, f"ade_rate_{_aid}"))
M.process_message(msg(S, "999"))
check("🔒 سرعت به سقف محدود شد", AD.get_ad(_aid)["rate"] <= 60,
      str(AD.get_ad(_aid)["rate"]))

# پیش‌نمایش و آزمایشی
SENT.clear()
M.handle_callback(cb(S, f"adprev_{_aid}"))
check("👁️ پیش‌نمایش کار کرد", "پیش‌نمایش" in alltext() or
      "دوره جدید" in alltext(), alltext()[-120:])
SENT.clear()
M.handle_callback(cb(S, f"adtest_{_aid}"))
check("📤 ارسال آزمایشی کار کرد",
      "آزمایشی" in alltext(), alltext()[-80:])


print("\n[۳.۲] 🚀 ارسال واقعی کمپین")

database.db_execute("UPDATE ad_campaigns SET target='all', rate=60 "
                    "WHERE id=?", (_aid,))
SENT.clear()
M.handle_callback(cb(S, f"adgo_{_aid}"))
check("تأیید قبل از ارسال", "تأیید" in last() or "مطمئن" in last(),
      last()[:80])
check("تعداد مخاطب نمایش داده شد", "نفر" in last())

# 🔴 باگ رفع‌شده (فاز ۴۰) — «تست وابسته به ساعت دیوار»:
#    `ads.in_quiet_hours()` به ساعت واقعی سیستم نگاه می‌کند
#    (پیش‌فرض: سکوت ۲۳ تا ۸). اگر تست بین ۲۳:۰۰ تا ۰۸:۰۰
#    اجرا می‌شد، `start_campaign` زودتر برمی‌گشت با پیام
#    «🌙 الان ساعت سکوت است» و این ۴ بررسی می‌افتادند:
#      ارسال انجام شد · وضعیت تمام‌شده · لاگ ثبت شد · A/B
#
#    همان کد، ساعت ۲۲:۰۰ پاس و ساعت ۲۳:۱۰ ناموفق می‌شد.
#    حالا ساعت سکوت را برای این بخش خاموش می‌کنیم تا نتیجه
#    قطعی و تکرارپذیر باشد. (تست خودِ ساعت سکوت جداست.)
database.db_execute("UPDATE ad_campaigns SET quiet_hours=0 "
                    "WHERE id=?", (_aid,))
SENT.clear()
AD.start_campaign(S, S, _aid, confirmed=True)
_a3 = AD.get_ad(_aid)
check("🚀 ارسال انجام شد", (_a3["sent_count"] or 0) > 0,
      str(_a3["sent_count"]))
check("وضعیت تمام‌شده", _a3["status"] == "done", _a3["status"])
_logs = database.db_scalar("SELECT COUNT(*) FROM ad_logs WHERE ad_id=?",
                           (_aid,)) or 0
check("📋 لاگ ارسال ثبت شد", _logs > 0, str(_logs))
check("🅱️ A/B هر دو نسخه رفت",
      (_a3["sent_a"] or 0) > 0 and (_a3["sent_b"] or 0) > 0,
      f"A={_a3['sent_a']} B={_a3['sent_b']}")

# کلیک
_first = database.db_execute("SELECT * FROM ad_logs WHERE ad_id=? LIMIT 1",
                             (_aid,), fetch="one")
_clicker = _first["bale_user_id"]
SENT.clear()
AD.click(_clicker, _clicker, _aid)
_a4 = AD.get_ad(_aid)
check("👆 کلیک ثبت شد", (_a4["click_count"] or 0) == 1,
      str(_a4["click_count"]))
check("📈 نرخ کلیک محاسبه می‌شود", AD.ctr(_a4) > 0, str(AD.ctr(_a4)))
AD.click(_clicker, _clicker, _aid)
check("🔒 کلیک تکراری دوبار شمرده نمی‌شود",
      (AD.get_ad(_aid)["click_count"] or 0) == 1)

_w, _ra, _rb = AD.ab_winner(_a4)
check("🏆 برنده A/B محاسبه می‌شود", _w in ("a", "b", "tie"), str(_w))


print("\n[۳.۳] 🛡️ احترام به کاربر")

check("تابع لغو اشتراک هست", hasattr(AD, "set_optout"))
AD.set_optout(U2, True)
check("🔕 لغو اشتراک ثبت شد", AD.user_opted_out(U2))
check("🟢 بقیه تحت تأثیر نیستند", not AD.user_opted_out(U1))

_n_before = AD.get_ad(_aid)["sent_count"]
database.db_execute("UPDATE ad_campaigns SET status='draft' WHERE id=?",
                    (_aid,))
database.db_execute("DELETE FROM ad_logs WHERE ad_id=?", (_aid,))
database.db_execute("UPDATE ad_campaigns SET sent_count=0 WHERE id=?",
                    (_aid,))
SENT.clear()
AD.start_campaign(S, S, _aid, confirmed=True)
_got = database.db_scalar(
    "SELECT COUNT(*) FROM ad_logs WHERE ad_id=? AND bale_user_id=?",
    (_aid, U2)) or 0
check("🔴 به کسی که لغو کرده ارسال نشد", _got == 0, str(_got))
AD.set_optout(U2, False)

SENT.clear()
AD.user_optout(U1, U1)
check("کاربر خودش می‌تواند لغو کند", AD.user_opted_out(U1))
check("پیام محترمانه داده شد", "💚" in last() or "مهم" in last(),
      last()[:80])
AD.set_optout(U1, False)

# سقف روزانه
database.set_setting("ads_daily_cap", "1", "t", "ads")
database.clear_settings_cache()
check("🚦 سقف روزانه خوانده می‌شود", AD.daily_cap() == 1)
check("🚦 کسی که امروز گرفته، رد می‌شود",
      AD.got_enough_today(_clicker))
database.set_setting("ads_daily_cap", "0", "t", "ads")
database.clear_settings_cache()
check("🚦 سقف صفر = بدون محدودیت",
      not AD.got_enough_today(_clicker))
database.set_setting("ads_daily_cap", "2", "t", "ads")
database.clear_settings_cache()

# ساعت سکوت
database.set_setting("ads_quiet_on", "0", "t", "ads")
database.clear_settings_cache()
check("🌙 با خاموش بودن، سکوت اعمال نمی‌شود",
      not AD.in_quiet_hours())
database.set_setting("ads_quiet_on", "1", "t", "ads")
# 🔴 اصلاح فاز ۴۰: بازهٔ «۰ تا ۲۳» ساعت ۲۳ را پوشش نمی‌دهد
#    (شرط `s <= h < e` است) پس این بررسی بین ۲۳:۰۰ و ۰۰:۰۰
#    می‌افتاد. بازهٔ «۰ تا ۲۴» همهٔ ساعت‌ها را می‌گیرد و
#    نتیجه قطعی می‌شود.
database.set_setting("ads_quiet_start", "0", "t", "ads")
database.set_setting("ads_quiet_end", "24", "t", "ads")
database.clear_settings_cache()
check("🌙 ساعت سکوت تشخیص داده می‌شود", AD.in_quiet_hours())
database.set_setting("ads_quiet_start", "23", "t", "ads")
database.set_setting("ads_quiet_end", "8", "t", "ads")
database.clear_settings_cache()


print("\n[۳.۴] 📊 گزارش و تنظیمات")

SENT.clear()
M.handle_callback(cb(S, "ad_report"))
check("📊 گزارش باز شد", "گزارش" in last(), last()[:50])
check("نرخ کلیک در گزارش هست", "کلیک" in last())

SENT.clear()
M.handle_callback(cb(S, "ad_settings"))
check("⚙️ تنظیمات باز شد", "تنظیمات تبلیغات" in last(), last()[:50])
M.handle_callback(cb(S, "adsb_ads_optout_btn"))
database.clear_settings_cache()
check("کلید تنظیم عوض شد",
      database.get_setting("ads_optout_btn", "1") == "0")
M.handle_callback(cb(S, "adsb_ads_optout_btn"))
database.clear_settings_cache()

M.handle_callback(cb(S, "adse_ads_daily_cap"))
M.process_message(msg(S, "5"))
database.clear_settings_cache()
check("عدد تنظیم ذخیره شد", AD.daily_cap() == 5)
database.set_setting("ads_daily_cap", "2", "t", "ads")
database.clear_settings_cache()

SENT.clear()
M.handle_callback(cb(S, "ad_tips"))
check("💡 راهنما باز شد", "تبلیغات مؤثر" in last() or "متن" in last(),
      last()[:60])

# کپی و حذف
SENT.clear()
M.handle_callback(cb(S, f"adcopy_{_aid}"))
_n_ads = database.db_scalar("SELECT COUNT(*) FROM ad_campaigns") or 0
check("♻️ کپی ساخته شد", _n_ads >= 2, str(_n_ads))
_copy = database.db_execute("SELECT * FROM ad_campaigns ORDER BY id DESC "
                            "LIMIT 1", fetch="one")
check("کپی پیش‌نویس است", _copy["status"] == "draft")
check("کپی آمار صفر دارد", (_copy["sent_count"] or 0) == 0)
M.handle_callback(cb(S, f"addel_{_copy['id']}"))
check("🗑️ حذف شد",
      not AD.get_ad(_copy["id"]))
check("🔒 لاگ‌های حذف‌شده هم پاک شدند",
      (database.db_scalar("SELECT COUNT(*) FROM ad_logs WHERE ad_id=?",
                          (_copy["id"],)) or 0) == 0)


# ═══════════ ۴) 🛡️ رگرسیون ═══════════
print("\n[۴] 🛡️ رگرسیون")

check("ستون ads_optout در users هست",
      "ads_optout" in {c["name"] for c in database.db_execute(
          "PRAGMA table_info(users)", fetch="all")})
check("جدول کمپین ساخته شده",
      bool(database.db_execute(
          "SELECT name FROM sqlite_master WHERE type='table' "
          "AND name='ad_campaigns'", fetch="one")))
check("جدول لاگ ساخته شده",
      bool(database.db_execute(
          "SELECT name FROM sqlite_master WHERE type='table' "
          "AND name='ad_logs'", fetch="one")))

check("کمپین ناموجود کرش نمی‌کند", AD.get_ad(99999) is None)
check("ctr با ورودی خالی", AD.ctr(None) == 0)
check("ab_winner با ورودی خالی", AD.ab_winner(None)[0] is None)
check("render با کمپین خالی",
      isinstance(AD._render_body({}, None), str))

SENT.clear()
AD.click(U1, U1, 99999)
check("کلیک روی کمپین حذف‌شده کرش نمی‌کند", True)

check("زمان‌بندی خودکار تابع دارد", hasattr(AD, "check_scheduled"))
check("زمان‌بندی بدون کمپین کرش نمی‌کند",
      isinstance(AD.check_scheduled(), int))

_main = (ROOT / "main.py").read_text(encoding="utf-8")
check("📣 کمپین زمان‌بندی‌شده در حلقه وصل شد",
      "ads_mod.check_scheduled()" in _main)
check("📣 دکمه تبلیغات در منوی اطلاع‌رسانی",
      "ad_panel" in (ROOT / "bale_api.py").read_text(encoding="utf-8"))

import activity_log as AL  # noqa: E402
for a in ("ad_created", "ad_sent"):
    check(f"لاگ فارسی «{a}» دارد", a in AL.ACTION_FA)

SENT.clear()
M.handle_callback(cb(U1, "u_support"))
check("نمای کاربر هنوز سالم است", "پشتیبانی" in last())
SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("هاب گواهینامه هنوز سالم است", "گواهینامه" in last())


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۰ پاس شدند!")
