"""
تست مهاجرت — سناریوی واقعی کاربر

🔴 این تست باگی را می‌گیرد که هیچ تست دیگری نمی‌گرفت:
   وقتی کاربر دیتابیس نسخه قبلی دارد و کد جدید را اجرا می‌کند،
   ستون‌های جدید باید خودکار اضافه شوند.

   قبلاً فقط جدول users مهاجرت داشت. events و بقیه با
   CREATE TABLE IF NOT EXISTS ساخته می‌شدند → ستون جدید اضافه نمی‌شد
   → INSERT شکست می‌خورد → «دکمه ذخیره کار نمی‌کند»
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="noramig_")
DB = f"{TMP}/old.db"

PASS, FAIL = [], []


def check(n, c, d=""):
    if c:
        PASS.append(n); print(f"  ✅ {n}")
    else:
        FAIL.append((n, d)); print(f"  ❌ {n}  {d}")


print("\n" + "=" * 62)
print("🧪 تست مهاجرت دیتابیس — سناریوی واقعی کاربر")
print("=" * 62)

print("\n[۱] ساخت دیتابیس «قدیمی» (نسخه فاز ۴/۵)")
c = sqlite3.connect(DB)
c.executescript("""
CREATE TABLE users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bale_user_id INTEGER UNIQUE,
  first_name TEXT, last_name TEXT, mobile TEXT,
  is_authenticated INTEGER DEFAULT 0,
  is_admin INTEGER DEFAULT 0,
  profile_status TEXT DEFAULT 'draft');

CREATE TABLE user_states(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bale_user_id INTEGER UNIQUE, state TEXT, data TEXT,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP);

-- جدول events نسخه قدیمی: فقط چند ستون
CREATE TABLE events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT, event_type TEXT, status TEXT DEFAULT 'draft',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE event_registrations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER, bale_user_id INTEGER, status TEXT);

INSERT INTO users(bale_user_id,first_name,last_name,mobile,is_authenticated,is_admin,profile_status)
 VALUES(100000001,'ادمین','اصلی','09120000000',1,1,'approved');
INSERT INTO users(bale_user_id,first_name,last_name,mobile,is_authenticated,profile_status)
 VALUES(555111,'کاربر','قدیمی','09121111111',1,'approved');

-- ⚠️ state خراب از باگ نسخه قبلی: نام NULL ولی داده هست
INSERT INTO user_states(bale_user_id,state,data,expires_at)
 VALUES(100000001,NULL,'{"step":5,"title":"جلسه نیمه‌کاره"}',datetime('now','+1 hour'));

-- رویداد قدیمی
INSERT INTO events(title,event_type,status) VALUES('رویداد قدیمی','meeting','published');
""")
c.commit(); c.close()

old_cols = len(sqlite3.connect(DB).execute("PRAGMA table_info(events)").fetchall())
check(f"دیتابیس قدیمی ساخته شد (events با {old_cols} ستون)", old_cols == 5)

os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001", "DB_PATH": DB,
    "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i", "FILES_DIR": f"{TMP}/f",
    "PROFILES_DIR": f"{TMP}/f/p", "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1", "BROADCAST_RATE": "999",
})

import bale_api  # noqa: E402

SENT = []


def _api(m, p=None, **k):
    SENT.append({"m": m, "p": p or {}})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    if m == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if m == "getChat":
        return {"ok": True, "result": {"title": "x"}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage", "p": {"chat_id": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT)}}


bale_api.api = _api
bale_api.send = _send
bale_api.send_or_edit = lambda cid, t, kb=None, mid=None, force_new=False: _send(cid, t, kb)
bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.answer_callback = lambda *a, **k: {"ok": True}
bale_api.set_context = lambda *a, **k: None
bale_api.clear_context = lambda *a, **k: None
bale_api.forget_menu = lambda c: None
bale_api.set_reaction = lambda *a, **k: {"ok": True}
bale_api.ask_review = lambda *a, **k: {"ok": True}
bale_api.get_chat = lambda c: _api("getChat")
bale_api.get_chat_member = lambda c, u: _api("getChatMember")
bale_api.send_invoice = lambda *a, **k: {"ok": True, "result": {"message_id": 1}}

import database, auth, profile as pf, admin as ad  # noqa: E402
import import_excel as ie, events as ev, attendance as att  # noqa: E402
import settings_admin as sa, main as M  # noqa: E402

for m in (database, auth, pf, ad, ie, ev, att, sa, M):
    if hasattr(m, "send"):
        m.send = _send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = bale_api.send_or_edit
    if hasattr(m, "send_photo"):
        m.send_photo = lambda *a, **k: {"ok": True}
    if hasattr(m, "forget_menu"):
        m.forget_menu = lambda c: None
ad.get_chat = lambda c: _api("getChat")
ev.send_invoice = bale_api.send_invoice
sa.get_bot_username = lambda: "nora_bot"

S, U = 100000001, 555111


print("\n[۲] اجرای کد جدید روی دیتابیس قدیمی")
database.init_db()
ev.init_event_tables()
att.init_attendance_tables()
database.seed_default_settings()
sa.seed_phase5_settings()
auth.ensure_super_admin(S)

new_cols = {c["name"] for c in database.db_execute(
    "PRAGMA table_info(events)", fetch="all")}
need = ["capacity", "is_paid", "price", "privacy", "has_attendance",
        "has_certificate", "has_ticket", "points_reward", "online_link",
        "start_date", "start_time", "poster", "invite_code", "organizer",
        "location_type", "location_address", "require_profile",
        "require_approval", "allow_waitlist", "price_vip"]
missing = [x for x in need if x not in new_cols]
check(f"🐛 ستون‌های events اضافه شد ({old_cols}→{len(new_cols)})",
      not missing, f"گمشده: {missing}")

reg_cols = {c["name"] for c in database.db_execute(
    "PRAGMA table_info(event_registrations)", fetch="all")}
for col in ["ticket_code", "amount_paid", "transaction_id", "attended",
            "payment_payload", "user_id"]:
    check(f"ستون event_registrations.{col}", col in reg_cols)

tables = {t["name"] for t in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")}
for t in ["transactions", "settings", "attendance_sessions",
          "attendance_records", "certificates", "profile_submissions",
          "force_join_channels", "otp_codes", "import_history", "user_actions"]:
    check(f"جدول {t} ساخته شد", t in tables)

check("داده‌های قدیمی حفظ شدند",
      database.db_scalar("SELECT COUNT(*) FROM users") == 2)
check("رویداد قدیمی حفظ شد",
      database.db_scalar("SELECT COUNT(*) FROM events") == 1)


print("\n[۳] 🐛 state خراب قدیمی پاکسازی شد")
broken = database.db_scalar(
    "SELECT COUNT(*) FROM user_states WHERE state IS NULL OR state=''")
check("🐛 هیچ state خرابی نماند", broken == 0, f"{broken} رکورد خراب")
check("ربات دیگر گیر نمی‌کند", auth.get_state_name(S) is None)


print("\n[۴] 🐛 حالا ساخت رویداد باید کار کند")


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"chat": {"id": uid}, "message_id": 9}}


def last():
    m = [s for s in SENT if s["m"] == "sendMessage"]
    return m[-1]["p"]["text"] if m else ""


SENT.clear()
M.handle_callback(cb(S, "ev_new"))
M.handle_callback(cb(S, "ev_go"))
flow = [("t", "کارگاه پس از مهاجرت"), ("t", "توضیحات"), ("c", "evt_workshop"),
        ("c", "evl_online"), ("t", "https://ble.ir/x"), ("t", "1404/07/15"),
        ("t", "18:00"), ("t", "120"), ("t", "30"), ("c", "evpay_1"),
        ("t", "250000"), ("c", "paym_bale_wallet"),
        ("c", "evp_public"), ("c", "evf_done"),
        ("t", "25"), ("t", "خط زندگی"), ("t", "⏭️ رد کردن")]
for k, v in flow:
    if k == "c":
        M.handle_callback(cb(S, v))
    else:
        M.process_message(msg(S, v))

check("پیش‌نمایش رسید", "پیش‌نمایش رویداد" in last(), last()[:60])

before = database.db_scalar("SELECT COUNT(*) FROM events")
M.handle_callback(cb(S, "ev_save_publish"))
after = database.db_scalar("SELECT COUNT(*) FROM events")
check("🐛🐛🐛 رویداد روی دیتابیس قدیمی ذخیره شد",
      after == before + 1, f"{before}→{after}  |  {last()[:80]}")

if after > before:
    e = database.db_execute("SELECT * FROM events ORDER BY id DESC LIMIT 1",
                            fetch="one")
    check("عنوان درست", e["title"] == "کارگاه پس از مهاجرت")
    check("قیمت ذخیره شد", e["price"] == 250000, str(e.get("price")))
    check("ظرفیت ذخیره شد", e["capacity"] == 30)
    check("امتیاز ذخیره شد", e["points_reward"] == 25)
    check("گواهینامه فعال (پیش‌فرض کارگاه)", e["has_certificate"] == 1)
    check("لینک ذخیره شد", e["online_link"] == "https://ble.ir/x")
    EID = e["id"]
else:
    EID = None


print("\n[۵] ثبت‌نام روی دیتابیس مهاجرت‌شده")
if EID:
    SENT.clear()
    M.handle_callback(cb(U, f"uev_{EID}"))
    check("کاربر رویداد را می‌بیند", "کارگاه پس از مهاجرت" in last())
    M.handle_callback(cb(U, f"ureg_{EID}"))
    r = database.db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (EID, U), fetch="one")
    check("🐛 ثبت‌نام روی جدول قدیمی کار کرد", bool(r), last()[:60])
    if r:
        check("وضعیت pending (پولی)", r["status"] == "pending")
        check("payload ذخیره شد", bool(r.get("payment_payload")))


print("\n[۶] حضور و غیاب روی دیتابیس مهاجرت‌شده")
if EID:
    database.db_execute(
        "UPDATE events SET has_attendance=1 WHERE id=?", (EID,))
    database.db_execute(
        "UPDATE event_registrations SET status='confirmed' WHERE event_id=?", (EID,))
    SENT.clear()
    M.handle_callback(cb(S, f"att_new_{EID}"))
    check("جلسه ساخته شد", "ساخته شد" in last(), last()[:60])
    # 🆕 فاز ۳۳: جلسات خودکار هم ساخته می‌شوند — جلسهٔ **باز** را بگیر
    sess = database.db_execute(
        "SELECT * FROM attendance_sessions WHERE is_open=1 "
        "ORDER BY id DESC LIMIT 1", fetch="one") or database.db_execute(
        "SELECT * FROM attendance_sessions ORDER BY id DESC LIMIT 1",
        fetch="one")
    check("جلسه در دیتابیس", bool(sess))
    if sess:
        SENT.clear()
        # 🆕 فاز ۳۳: مستقیم همان جلسه را انتخاب کن
        #    (چون حالا چند جلسهٔ خودکار هم وجود دارد)
        M.handle_callback(cb(U, f"uatts_{sess['id']}"))
        M.process_message(msg(U, sess["session_code"]))
        rec = database.db_execute(
            "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
            (sess["id"], U), fetch="one")
        check("🐛 حضور ثبت شد", bool(rec), last()[:60])


print("\n[۷] گواهینامه روی دیتابیس مهاجرت‌شده")
if EID:
    database.db_execute("UPDATE events SET has_certificate=1 WHERE id=?", (EID,))
    cert = att.issue_certificate(U, S, EID, target_uid=U, silent=True)
    check("🐛 گواهینامه صادر شد", bool(cert))
    # 🆕 فاز ۳۴: سریال حالا شناسهٔ دولایه است (شمارهٔ نامه + کد فردی)
    #    اگر رویداد شمارهٔ نامه نداشته باشد، فقط کد فردی.
    _sn = (cert or {}).get("serial") or ""
    check("سریال دارد", bool(_sn) and len(_sn) >= 4, _sn)
    check("کد فردی ثبت شد", bool((cert or {}).get("person_code")),
          str((cert or {}).get("person_code")))


print("\n[۸] پیام همگانی روی دیتابیس مهاجرت‌شده")
SENT.clear()
M.handle_callback(cb(S, "admin_broadcast"))
check("منوی فیلتر باز شد", "اطلاع‌رسانی همگانی" in last())
check("شمارش کار می‌کند", ad.bc_count("all") >= 2, str(ad.bc_count("all")))
M.handle_callback(cb(S, "bcf_all"))
M.process_message(msg(S, "پیام تست بعد از مهاجرت"))
check("پیش‌نمایش", "پیش‌نمایش نهایی" in last())
SENT.clear()
M.handle_callback(cb(S, "bc_go"))
got = [s for s in SENT if s["m"] == "sendMessage"
       and s["p"].get("chat_id") == U
       and "پیام تست بعد از مهاجرت" in (s["p"].get("text") or "")]
check("🐛 پیام همگانی رسید", len(got) >= 1, f"{len(got)}")


print("\n[۹] دعوت لینکی روی دیتابیس مهاجرت‌شده")
SENT.clear()
M.handle_callback(cb(U, "u_referral"))
check("🐛 لینک ساخته شد", "https://ble.ir/nora_bot?start=" in last(), last()[:120])
check("کد معرف پر شده",
      bool((auth.get_user(U) or {}).get("referral_code")))


print("\n[۱۰] اجرای دوباره init (باید بی‌خطر باشد)")
n_before = len({c["name"] for c in database.db_execute(
    "PRAGMA table_info(events)", fetch="all")})
database.init_db()
ev.init_event_tables()
att.init_attendance_tables()
n_after = len({c["name"] for c in database.db_execute(
    "PRAGMA table_info(events)", fetch="all")})
check("مهاجرت idempotent است", n_before == n_after, f"{n_before}→{n_after}")
check("داده‌ها حفظ شدند",
      database.db_scalar("SELECT COUNT(*) FROM events") >= 2)


print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 مهاجرت از نسخه قدیمی سالم است!")
sys.exit(0)
