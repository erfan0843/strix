"""
تست فاز ۶ + بررسی باگ‌های گزارش‌شده کاربر

پوشش:
  🐛 باگ‌های گزارش‌شده: پیام همگانی، ذخیره رویداد، ویرایش در جا،
     state گم شدن، دعوت لینکی
  ✋ حضور و غیاب (۵ روش)
  🎓 گواهینامه
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora6_")
os.environ.update({
    "BOT_TOKEN": "1095412158:TEST", "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "k", "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l",
    "BROADCAST_RATE": "1000", "STATE_TTL_MINUTES": "120",
})

import bale_api  # noqa: E402

SENT, EDITS, REACTIONS = [], [], []


def _api(m, p=None, **k):
    p = p or {}
    SENT.append({"method": m, "params": p})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot", "first_name": "نورا"}}
    if m == "editMessageText":
        EDITS.append(p)
        return {"ok": True, "result": {"message_id": p.get("message_id")}}
    if m == "setMessageReaction":
        REACTIONS.append(p)
        return {"ok": True}
    if m in ("getChatMember",):
        return {"ok": True, "result": {"status": "member"}}
    if m == "getChat":
        return {"ok": True, "result": {"title": "x"}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"method": "sendMessage",
                 "params": {"chat_id": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT)}}


bale_api.api = _api
bale_api.send = _send


def _soe_early(cid, text, kb=None, mid=None, force_new=False):
    return _send(cid, text, kb)


bale_api.send_or_edit = _soe_early
bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.answer_callback = lambda *a, **k: {"ok": True}
bale_api.get_chat = lambda c: _api("getChat")
bale_api.get_chat_member = lambda c, u: _api("getChatMember")
bale_api.set_reaction = lambda c, m, e=None, b=False: _api(
    "setMessageReaction", {"chat_id": c, "message_id": m, "emoji": e or "👍"})
bale_api.ask_review = lambda u, d=5: {"ok": True}
bale_api.get_me = lambda: {"ok": True, "result": {"username": "nora_bot"}}
bale_api.send_invoice = lambda *a, **k: {"ok": True, "result": {"message_id": 1}}
bale_api.answer_pre_checkout_query = lambda *a, **k: {"ok": True}

import database, auth, profile as pf, admin as ad  # noqa: E402
import import_excel as ie, events as ev, attendance as att  # noqa: E402
import settings_admin as sa, main as M, config  # noqa: E402

MODS = (database, auth, pf, ad, ie, ev, att, sa, M)
for m in MODS:
    if hasattr(m, "send"):
        m.send = _send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = _soe_early
    if hasattr(m, "send_photo"):
        m.send_photo = lambda *a, **k: {"ok": True}
    if hasattr(m, "send_document"):
        m.send_document = lambda *a, **k: {"ok": True}
ad.get_chat = lambda c: _api("getChat")
M.set_reaction = bale_api.set_reaction
ev.send_invoice = bale_api.send_invoice
ev.answer_pre_checkout_query = bale_api.answer_pre_checkout_query
sa.get_bot_username = lambda: "nora_bot"

S = 100000001
U1, U2, U3 = 111111, 222222, 333333
PASS, FAIL = [], []


def check(n, c, d=""):
    if c:
        PASS.append(n); print(f"  ✅ {n}")
    else:
        FAIL.append((n, d)); print(f"  ❌ {n}  {d}")


def last(n=1):
    m = [s for s in SENT if s["method"] == "sendMessage"]
    return m[-n]["params"]["text"] if len(m) >= n else ""


def texts():
    return [s["params"]["text"] for s in SENT if s["method"] == "sendMessage"]


def to(cid):
    return [s["params"]["text"] for s in SENT
            if s["method"] == "sendMessage" and s["params"].get("chat_id") == cid]


def kbl():
    """برچسب دکمه‌ها — هم شیشه‌ای هم پایین صفحه (فاز ۹: منوی اصلی پایین است)"""
    m = [s for s in SENT if s["method"] in ("sendMessage", "editMessageText")]
    for s in reversed(m):
        kb = s["params"].get("kb") or {}
        rows = kb.get("inline_keyboard") or kb.get("keyboard") or []
        out = []
        for r in rows:
            for b in r:
                out.append(b["text"] if isinstance(b, dict) else str(b))
        if out:
            return out
    return []


def msg(uid, t, mid=1):
    return {"message_id": mid, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"chat": {"id": uid}, "message_id": 9}}


def mkuser(uid, name="کاربر", **kw):
    cols = {"bale_user_id": uid, "first_name": name, "last_name": "تست",
            "mobile": f"0912{uid:07d}"[:11], "is_authenticated": 1,
            "profile_status": "approved", "referral_code": f"NORA{uid}"}
    cols.update(kw)
    k = list(cols.keys())
    database.db_execute(
        f"INSERT OR REPLACE INTO users ({','.join(k)}) VALUES ({','.join('?'*len(k))})",
        [cols[x] for x in k])


print("\n" + "=" * 62)
print("🧪 تست فاز ۶ + باگ‌های گزارش‌شده")
print("=" * 62)

print("\n[۱] راه‌اندازی")
database.init_db(); ev.init_event_tables(); att.init_attendance_tables()
database.seed_default_settings(); sa.seed_phase5_settings()
auth.ensure_super_admin(S)
tb = [t["name"] for t in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")]
for t in ("attendance_sessions", "attendance_records", "certificates"):
    check(f"جدول {t}", t in tb)


print("\n[۲] 🐛 باگ: state وسط ویزارد گم می‌شود")
auth.set_state(U1, "ev_create", {"step": 3, "title": "تست"}, merge=False)
database.db_execute(
    "UPDATE user_states SET expires_at=datetime('now','-2 hour') WHERE bale_user_id=?",
    (U1,))
check("state منقضی شد", auth.get_state_name(U1) is None)
auth.update_state_data(U1, {"event_type": "meeting"})
check("🐛 نام state بازیابی شد (NULL نشد)",
      auth.get_state_name(U1) == "ev_create", str(auth.get_state_name(U1)))
check("🐛 داده قبلی حفظ شد",
      auth.get_state_data(U1).get("title") == "تست", str(auth.get_state_data(U1)))
check("داده جدید هم اضافه شد",
      auth.get_state_data(U1).get("event_type") == "meeting")
auth.clear_state(U1)


print("\n[۳] 🐛 باگ: دکمه ذخیره رویداد کار نمی‌کند")
SENT.clear()
M.handle_callback(cb(S, "ev_new")); M.handle_callback(cb(S, "ev_go"))
flow = [("t", "همایش سالانه"), ("t", "توضیحات همایش"), ("c", "evt_conference"),
        ("c", "evl_physical"), ("t", "تهران سالن اصلی"), ("t", "1404/07/10"),
        ("t", "09:00"), ("t", "180"), ("t", "100"), ("c", "evpay_0"),
        ("c", "evp_public"), ("c", "evf_done"), ("t", "15"),
        ("t", "خط زندگی"), ("t", "⏭️ رد کردن")]
for k, v in flow:
    if k == "c":
        M.handle_callback(cb(S, v))
    else:
        M.process_message(msg(S, v))
check("پیش‌نمایش رسید", "پیش‌نمایش رویداد" in last())

before = database.db_scalar("SELECT COUNT(*) FROM events")
M.handle_callback(cb(S, "ev_save_publish"))
after = database.db_scalar("SELECT COUNT(*) FROM events")
check("🐛 رویداد ذخیره شد", after == before + 1, f"{before}→{after}")
check("پیام تأیید با جزئیات", "با موفقیت ذخیره شد" in last())
E1 = database.db_execute("SELECT * FROM events ORDER BY id DESC LIMIT 1", fetch="one")
check("عنوان درست", E1["title"] == "همایش سالانه")
check("همه فیلدها", E1["capacity"] == 100 and E1["points_reward"] == 15
      and E1["status"] == "published")
check("state پاک شد", auth.get_state(S) is None)

# سناریو: state گم شده، ذخیره باید پیام واضح بدهد
SENT.clear()
auth.clear_state(S)
M.handle_callback(cb(S, "ev_save_publish"))
check("🐛 وقتی state نیست پیام واضح می‌دهد",
      "پیدا نشد" in last() and "دوباره" in last(), last()[:60])
check("دکمه ساخت دوباره دارد", any("ساخت دوباره" in x for x in kbl()))

# بازیابی از رکورد منقضی
auth.set_state(S, "ev_create", {"title": "بازیابی شده", "event_type": "meeting",
                                "location_type": "online",
                                "start_date": "1404/08/01"}, merge=False)
database.db_execute(
    "UPDATE user_states SET expires_at=datetime('now','-3 hour') WHERE bale_user_id=?",
    (S,))
SENT.clear()
b2 = database.db_scalar("SELECT COUNT(*) FROM events")
M.handle_callback(cb(S, "ev_save_draft"))
a2 = database.db_scalar("SELECT COUNT(*) FROM events")
check("🐛 حتی از state منقضی هم بازیابی می‌کند", a2 == b2 + 1, f"{b2}→{a2}")


print("\n[۴] 🐛 باگ: هر کلیک پیام جدید می‌سازد")
# نسخه واقعی send_or_edit را موقتاً فعال می‌کنیم
import importlib
_real_soe = importlib.import_module("bale_api").__dict__
_saved = {}


def _real_send_or_edit(cid, text, kb=None, mid=None, force_new=False):
    """نسخه ساده‌شده منطق واقعی برای تست"""
    target = mid or _CTX.get(cid)
    if force_new or not target or (kb and ("keyboard" in (kb or {}))):
        return _send(cid, text, kb)
    EDITS.append({"chat_id": cid, "message_id": target, "text": text})
    return {"ok": True, "result": {"message_id": target}}


_CTX = {}
for m in MODS:
    if hasattr(m, "send_or_edit"):
        _saved[m.__name__] = m.send_or_edit
        m.send_or_edit = _real_send_or_edit

EDITS.clear(); SENT.clear()
_CTX[S] = 777          # شبیه‌سازی: کلیک روی پیام ۷۷۷
M.handle_callback(cb(S, "admin_panel"))
M.handle_callback(cb(S, "admin_users"))
M.handle_callback(cb(S, "admin_panel"))
check("🐛 کلیک بعدی پیام را ویرایش می‌کند", len(EDITS) >= 2,
      f"{len(EDITS)} ویرایش")
check("همه روی پیام درست", all(e["message_id"] == 777 for e in EDITS),
      str([e["message_id"] for e in EDITS]))
check("پیام جدید کمتر ساخته شد",
      len([x for x in SENT if x["method"] == "sendMessage"]) <= 1,
      str(len([x for x in SENT if x["method"] == "sendMessage"])))

# برگرداندن mock
for m in MODS:
    if m.__name__ in _saved:
        m.send_or_edit = _saved[m.__name__]

print("\n[۵] 🐛 باگ: پیام همگانی و فیلترها")
for i, u in enumerate([U1, U2, U3]):
    mkuser(u, f"کاربر{i}",
           gender="مرد" if i % 2 == 0 else "زن",
           city="تهران" if i < 2 else "قم",
           is_vip=1 if i == 0 else 0)

SENT.clear()
M.handle_callback(cb(S, "admin_broadcast"))
check("منوی فیلتر باز شد", "اطلاع‌رسانی همگانی" in last())
labels = kbl()
check("🐛 فیلترها نمایش داده شدند", len(labels) >= 8, f"{len(labels)} فیلتر")
check("فیلتر VIP هست", any("VIP" in x for x in labels))
check("فیلتر جنسیت هست", any("آقایان" in x for x in labels))
check("فیلتر شهر هست", any("شهر" in x for x in labels))
check("تعداد در دکمه نمایش داده شده", any("(" in x for x in labels))

check("شمارش all", ad.bc_count("all") == 4, str(ad.bc_count("all")))
check("شمارش vip", ad.bc_count("vip") == 1, str(ad.bc_count("vip")))
check("شمارش male", ad.bc_count("male") == 2, str(ad.bc_count("male")))
check("شمارش female", ad.bc_count("female") == 1, str(ad.bc_count("female")))
check("شمارش شهر تهران", ad.bc_count("city", "تهران") == 2)

SENT.clear()
M.handle_callback(cb(S, "bcf_vip"))
check("فیلتر VIP انتخاب شد",
      any("مخاطب" in t or "متن پیام" in t for t in texts()), last()[:60])
d = auth.get_state_data(S)
check("filter در state ذخیره شد", d.get("filter") == "vip", str(d))

M.process_message(msg(S, "سلام به اعضای ویژه"))
check("پیش‌نمایش نمایش داده شد", "پیش‌نمایش نهایی" in last())
check("تعداد گیرنده درست", "1 نفر" in last(), last()[-200:])
d = auth.get_state_data(S)
check("🐛 ready ذخیره شد", d.get("ready") == 1, str(d))
check("🐛 متن حفظ شد", d.get("text") == "سلام به اعضای ویژه")
check("🐛 فیلتر حفظ شد", d.get("filter") == "vip")

SENT.clear()
M.handle_callback(cb(S, "bc_go"))
check("🐛 ارسال انجام شد", any("اطلاع‌رسانی تمام شد" in t for t in texts()))
vip_msgs = [t for t in to(U1) if "سلام به اعضای ویژه" in t]
check("🐛 فقط به VIP رفت", len(vip_msgs) == 1, str(len(vip_msgs)))
check("🐛 به غیر VIP نرفت",
      not any("سلام به اعضای ویژه" in t for t in to(U2)))

# فیلتر شهر
SENT.clear()
M.handle_callback(cb(S, "admin_broadcast"))
M.handle_callback(cb(S, "bcf_city"))
check("درخواست نام شهر", "شهر" in last())
M.process_message(msg(S, "قم"))
check("شهر پذیرفته شد", "1 نفر" in last() or "قم" in last())
M.process_message(msg(S, "پیام مخصوص قم"))
SENT.clear()
M.handle_callback(cb(S, "bc_go"))
check("🐛 فیلتر شهر کار کرد", any("پیام مخصوص قم" in t for t in to(U3)))
check("به تهرانی‌ها نرفت", not any("پیام مخصوص قم" in t for t in to(U1)))

# بدون ready
auth.clear_state(S)
SENT.clear()
M.handle_callback(cb(S, "bc_go"))
check("بدون آماده‌سازی پیام واضح می‌دهد", "پیدا نشد" in last())


print("\n[۶] 🐛 باگ: دعوت دوستان لینکی")
SENT.clear()
M.handle_callback(cb(U1, "u_referral"))
t = last()
check("صفحه دعوت باز شد", "دعوت از دوستان" in t)
check("🐛 لینک قابل کلیک دارد", "https://ble.ir/nora_bot?start=" in t, t[:200])
check("کد در لینک هست", f"NORA{U1}" in t)
check("آمار دعوت دارد", "دعوت‌شده" in t)
check("دکمه کپی لینک", any("کپی لینک" in x for x in kbl()))
check("دکمه متن آماده", any("متن آماده" in x for x in kbl()))

SENT.clear()
M.handle_callback(cb(U1, "u_ref_share"))
check("متن آماده اشتراک", "برای عضویت" in " ".join(texts()))

# ثبت رابطه دعوت
NEWU = 444444
SENT.clear()
M.process_message(msg(NEWU, f"/start NORA{U1}"))
check("کاربر جدید وارد شد", True)
mkuser(NEWU, "تازه‌وارد")
SENT.clear()
M.process_message(msg(NEWU, f"/start NORA{U1}"))
row = database.db_execute("SELECT referred_by FROM users WHERE bale_user_id=?",
                          (NEWU,), fetch="one")
check("🐛 رابطه دعوت ثبت شد", row and row.get("referred_by") == U1, str(row))
check("به دعوت‌کننده اطلاع رفت",
      any("با لینک شما عضو شد" in x for x in to(U1)))
SENT.clear()
M.handle_callback(cb(U1, "u_referral"))
check("آمار دعوت به‌روز شد", "1 نفر" in last())
SENT.clear()
M.handle_callback(cb(U1, "u_ref_list"))
check("لیست دعوت‌شده‌ها", "تازه‌وارد" in last())


print("\n[۷] ✋ حضور و غیاب — ساخت جلسه")
eid = database.db_execute("""INSERT INTO events
    (title,event_type,location_type,start_date,status,is_paid,has_attendance,
     has_certificate,has_ticket,require_profile,points_reward,created_by)
    VALUES ('کارگاه تست','workshop','physical','1404/07/01','published',0,1,1,1,0,10,?)""",
    (S,))
for u in (U1, U2, U3):
    uu = auth.get_user(u)
    database.db_execute("""INSERT INTO event_registrations
        (event_id,user_id,bale_user_id,status,ticket_code)
        VALUES (?,?,?,'confirmed',?)""", (eid, uu["id"], u, f"T{u}"))

SENT.clear()
M.handle_callback(cb(S, f"ev_view_{eid}"))
check("دکمه حضور و غیاب در رویداد", any("حضور و غیاب" in x for x in kbl()))
check("دکمه گواهینامه در رویداد", any("گواهینامه" in x for x in kbl()))

SENT.clear()
M.handle_callback(cb(S, f"att_list_{eid}"))
check("صفحه جلسات", "حضور و غیاب" in last())
M.handle_callback(cb(S, f"att_new_{eid}"))
check("جلسه ساخته شد", "ساخته شد" in last())
sess = database.db_execute("SELECT * FROM attendance_sessions ORDER BY id DESC LIMIT 1",
                           fetch="one")
check("در دیتابیس ثبت شد", bool(sess))
check("کد ۵ رقمی", len(sess["session_code"]) == 5 and sess["session_code"].isdigit())
check("باز است", sess["is_open"] == 1)
SID, CODE = sess["id"], sess["session_code"]

# 🔴 اصلاح فاز ۳۵ — از فاز ۳۳ به بعد، «رویداد» هنگام ساخت
#    خودش یک جلسهٔ خودکار می‌سازد. این تست از فاز ۶ است و
#    فرض می‌کند فقط **یک** جلسهٔ باز وجود دارد؛ با دو جلسهٔ باز
#    ربات درست‌کارانه اول می‌پرسد «کدام جلسه؟» و تست می‌شکست.
#    این رفتار درست است — پس اینجا سناریوی تک‌جلسه‌ای را
#    بازمی‌سازیم و جلسه‌های خودکار را می‌بندیم.
_auto = database.db_execute(
    "UPDATE attendance_sessions SET is_open=0 "
    "WHERE event_id=? AND id<>?", (eid, SID))


print("\n[۸] ✋ ثبت حضور — روش کد جلسه")
SENT.clear()
M.handle_callback(cb(U1, "u_attendance"))
check("منوی حضور کاربر", "حضور و غیاب" in last())
check("رویداد در لیست", any("کارگاه تست" in x for x in kbl()))

M.handle_callback(cb(U1, f"uatt_{eid}"))
check("درخواست کد", "کد حضور" in last())
M.process_message(msg(U1, "00000"))
check("کد اشتباه رد شد", "اشتباه" in last())

pts_before = auth.get_user(U1)["total_points"] or 0
SENT.clear()
M.process_message(msg(U1, CODE))
check("🎯 حضور ثبت شد", "حضور شما ثبت شد" in " ".join(texts()))
rec = database.db_execute(
    "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
    (SID, U1), fetch="one")
check("رکورد در دیتابیس", bool(rec) and rec["status"] == "present")
check("روش code", rec["method"] == "code")
pts_after = auth.get_user(U1)["total_points"] or 0
check("🏆 امتیاز داده شد", pts_after == pts_before + 10, f"{pts_before}→{pts_after}")
reg = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (eid, U1), fetch="one")
check("وضعیت ثبت‌نام attended", reg["status"] == "attended" and reg["attended"] == 1)

SENT.clear()
M.handle_callback(cb(U1, f"uatt_{eid}"))
check("حضور تکراری جلوگیری شد", "قبلاً ثبت شده" in last())


print("\n[۹] ✋ ثبت حضور با کد بلیت")
SENT.clear()
M.handle_callback(cb(U2, f"uatt_{eid}"))
M.process_message(msg(U2, f"T{U2}"))
check("🎫 با کد بلیت هم ثبت شد", "حضور شما ثبت شد" in " ".join(texts()))
r2 = database.db_execute(
    "SELECT method FROM attendance_records WHERE session_id=? AND bale_user_id=?",
    (SID, U2), fetch="one")
check("روش ticket", r2 and r2["method"] == "ticket")


print("\n[۱۰] ✍️ ثبت دستی ادمین")
SENT.clear()
M.handle_callback(cb(S, f"att_manual_{SID}_0"))
check("لیست ثبت دستی", "ثبت دستی" in last())
check("چک‌باکس دارد", any("⬜" in x or "✅" in x for x in kbl()))
M.handle_callback(cb(S, f"attm_{SID}_{U3}_0"))
r3 = database.db_execute(
    "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
    (SID, U3), fetch="one")
check("👨‍💼 دستی ثبت شد", bool(r3) and r3["method"] == "manual")
M.handle_callback(cb(S, f"attm_{SID}_{U3}_0"))
r3b = database.db_execute(
    "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
    (SID, U3), fetch="one")
check("تاگل حذف هم کار می‌کند", r3b is None)
M.handle_callback(cb(S, f"attm_{SID}_{U3}_0"))


print("\n[۱۱] 📍 حضور با موقعیت مکانی")
database.db_execute(
    "UPDATE attendance_sessions SET method='location', lat=35.7, lon=51.4, radius_m=200 "
    "WHERE id=?", (SID,))
database.db_execute("DELETE FROM attendance_records WHERE session_id=? AND bale_user_id=?",
                    (SID, U1))
SENT.clear()
M.handle_callback(cb(U1, f"uatt_{eid}"))
check("درخواست موقعیت", "موقعیت" in last())
M.process_update({"update_id": 1, "message": {
    "message_id": 5, "from": {"id": U1}, "chat": {"id": U1, "type": "private"},
    "location": {"latitude": 35.9, "longitude": 51.9}}})
check("📍 دور بودن تشخیص داده شد", "در محل رویداد نیستید" in last(), last()[:60])
M.process_update({"update_id": 2, "message": {
    "message_id": 6, "from": {"id": U1}, "chat": {"id": U1, "type": "private"},
    "location": {"latitude": 35.7005, "longitude": 51.4005}}})
check("📍 نزدیک بودن پذیرفته شد", "حضور شما ثبت شد" in " ".join(texts()))
database.db_execute("UPDATE attendance_sessions SET method='code' WHERE id=?", (SID,))


print("\n[۱۲] 📢 اعلام کد + بستن جلسه")
SENT.clear()
M.handle_callback(cb(S, f"att_announce_{SID}"))
check("کد اعلام شد", any("اعلام شد" in t for t in texts()))
check("به شرکت‌کننده رسید", any("کد حضور" in t for t in to(U2)))

M.handle_callback(cb(S, f"att_toggle_{SID}"))
s2 = database.db_execute("SELECT is_open FROM attendance_sessions WHERE id=?",
                         (SID,), fetch="one")
check("جلسه بسته شد", s2["is_open"] == 0)
database.db_execute("DELETE FROM attendance_records WHERE session_id=? AND bale_user_id=?",
                    (SID, U3))
SENT.clear()
M.handle_callback(cb(U3, f"uatt_{eid}"))
check("جلسه بسته → ثبت ممکن نیست",
      "جلسه بازی" in last() or "بسته" in last(), last()[:60])
M.handle_callback(cb(S, f"att_toggle_{SID}"))


print("\n[۱۳] 📊 کارنامه و گزارش")
SENT.clear()
M.handle_callback(cb(U1, "u_att_report"))
check("کارنامه کاربر", "کارنامه حضور" in last())
check("آمار دارد", "کل حضور" in last())

M.handle_callback(cb(S, f"att_report_{eid}"))
check("گزارش ادمین", "کارنامه" in last())
check("نرخ حضور", "میانگین" in last() or "جلسه" in last())

M.handle_callback(cb(S, f"att_who_{SID}_0"))
check("لیست حاضرین", "حاضرین" in last())

try:
    import openpyxl  # noqa
    M.handle_callback(cb(S, f"att_export_{eid}"))
    fs = list(Path(TMP, "i").glob("attendance_*.xlsx"))
    check("📤 خروجی اکسل حضور", len(fs) >= 1)
except ImportError:
    print("  ⚠️ openpyxl نیست")


print("\n[۱۴] 🎓 گواهینامه")
SENT.clear()
M.handle_callback(cb(S, "cert_settings"))
check("تنظیمات گواهینامه", "تنظیمات گواهینامه" in last())
check("متغیرها نمایش داده شد", "{name}" in last())

M.handle_callback(cb(S, "cert_preview"))
check("پیش‌نمایش گواهینامه", "علی محمدی" in " ".join(texts()))

M.handle_callback(cb(S, "cert_edit"))
check("ویرایش شروع شد", "ویرایش قالب" in last())
M.process_message(msg(S, "🎓 گواهینامه ویژه\n\n{name}\nدر {event}\n{serial}"))
check("قالب ذخیره شد", "گواهینامه ویژه" in database.get_setting("cert_template"))

SENT.clear()
c = att.issue_certificate(U1, S, eid, target_uid=U1, silent=True)
check("🎓 گواهینامه صادر شد", bool(c))
check("شماره سریال دارد", c and c["serial"].startswith("NORA-"))
check("نام در گواهینامه", c and "کاربر0" in c["template"])
check("عنوان رویداد در گواهینامه", c and "کارگاه تست" in c["template"])
u1 = auth.get_user(U1)
check("شمارنده گواهینامه کاربر", (u1.get("total_certificates") or 0) >= 1)

c2 = att.issue_certificate(U1, S, eid, target_uid=U1, silent=True)
check("گواهینامه تکراری صادر نمی‌شود",
      c2 and c2["id"] == c["id"], "دو گواهینامه ساخته شد!")

SENT.clear()
M.handle_callback(cb(U1, "u_my_certs"))
check("گواهینامه‌های من", "گواهینامه‌های من" in last())
check("گواهینامه در لیست", "کارگاه تست" in last())

SENT.clear()
M.handle_callback(cb(S, f"cert_bulk_{eid}"))
check("تأیید صدور گروهی", "صدور گروهی" in last())
M.handle_callback(cb(S, f"cert_bulky_{eid}"))
check("صدور گروهی انجام شد", "صدور گروهی تمام شد" in " ".join(texts()))
total_c = database.db_scalar("SELECT COUNT(*) FROM certificates WHERE event_id=?", (eid,))
check("گواهینامه برای همه صادر شد", total_c == 3, str(total_c))
check("به کاربران ارسال شد", any("گواهینامه شما صادر شد" in t for t in to(U2)))


print("\n[۱۵] منوها طبق معماری")
SENT.clear()
M.handle_callback(cb(U1, "back_main"))
labels = kbl()
expected = ["رویدادها", "پروفایل من", "حضور و غیاب", "دعوت از دوستان",
            "اعلان‌ها", "پشتیبانی"]
for e in expected:
    check(f"منوی کاربر: {e}", any(e in x for x in labels), str(labels))
check("حضور و غیاب دیگر «به زودی» نیست",
      not any("حضور و غیاب (به زودی)" in x for x in labels))

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
al = kbl()
# فاز ۱۳: پنل ادمین از ۱۲ دکمه به ۷ دکمه خلوت شد.
# «تعریف رویداد جدید» و «رویدادهای من» داخل «رویدادها» رفتند و
# «داشبورد گزارشات» به «گزارش‌ها» تغییر نام داد.
for e in ["رویدادها", "فرم\u200cساز", "اطلاع\u200cرسانی",
          "مدیریت کاربران", "گزارش", "تنظیمات"]:
    check(f"منوی ادمین: {e}", any(e in x for x in al), str(al))

SENT.clear()
M.handle_callback(cb(U1, "profile_view"))
pl = kbl()
# 🔄 فاز ۳۸: منوی پروفایل جمع‌وجور شد — برچسب‌ها کوتاه‌تر
#    شدند («🎫 بلیت‌ها» به‌جای «🎫 بلیت‌های من») و دکمهٔ عکس
#    داخل خودِ فرم پروفایل رفت. اینجا ریشهٔ کلمه را می‌سنجیم.
for e in ["بلیت", "گواهینامه", "امتیاز", "کارنامه حضور"]:
    check(f"پروفایل: {e}", any(e in x for x in pl), str(pl))

SENT.clear()
M.handle_callback(cb(S, "admin_settings"))
sl = kbl()
for e in ["مدیریت متن‌ها", "عضویت اجباری", "پرداخت", "OTP سفیر",
          "گواهینامه و بلیط"]:
    check(f"تنظیمات: {e}", any(e in x for x in sl), str(sl))


print("\n[۱۶] امنیت")
for d, w in [("att_new_1", "دسترسی"), ("cert_bulk_1", "دسترسی"),
             (f"att_manual_{SID}_0", "دسترسی"), ("cert_settings", "دسترسی"),
             ("admin_broadcast", "دسترسی"), ("bcf_all", "دسترسی")]:
    SENT.clear()
    M.handle_callback(cb(U1, d))
    check(f"🔒 کاربر عادی: {d}", w in last(), last()[:40])


print("\n[۱۷] ورودی‌های خراب")
weird = [
    {"update_id": 20, "callback_query": {"id": "x", "from": {"id": S},
     "data": "att_view_abc", "message": {"chat": {"id": S}}}},
    {"update_id": 21, "callback_query": {"id": "x", "from": {"id": S},
     "data": "attm_", "message": {"chat": {"id": S}}}},
    {"update_id": 22, "callback_query": {"id": "x", "from": {"id": S},
     "data": "att_who_", "message": {"chat": {"id": S}}}},
    {"update_id": 23, "callback_query": {"id": "x", "from": {"id": U1},
     "data": "ucertv_9999", "message": {"chat": {"id": U1}}}},
    {"update_id": 24, "callback_query": {"id": "x", "from": {"id": S},
     "data": "bcf_nonexistent", "message": {"chat": {"id": S}}}},
    {"update_id": 25, "callback_query": {"id": "x", "from": {"id": S},
     "data": "bce_abc", "message": {"chat": {"id": S}}}},
    {"update_id": 26, "message": {"from": {"id": U1},
     "chat": {"id": U1, "type": "private"}, "location": {"latitude": 1}}},
]
crash = 0
for w in weird:
    try:
        M.process_update(w)
    except Exception as e:
        crash += 1
        print(f"      💥 {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", crash == 0, f"{crash} کرش")


print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۶ پاس شدند!")
sys.exit(0)
