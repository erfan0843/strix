"""
تست فاز ۲۲ — ✋ حضور و غیاب کامل · 🎓 مرکز صدور گواهینامه

درخواست کاربر (عیناً):
  «حضور و غیاب رویداد واقعا ضعیف و داغونه و گواهینامه تو مدیریت
   رویداد صادر نمیشه، صدور گواهینامه... کامل و دقیق و با جزییات و
   انتخاب قالب و تغییر پارامترها... کامل و دقیق بیار تو صدور
   گواهینامه گروهی رویداد، خلاصه بخشش رو کامل کن»

چهار باگ ریشه‌ای:
  ۱) صدور گروهی فایل نمی‌فرستاد — silent=True و بعد فقط متن خام
  ۲) شرط حضور (cert_condition/cert_min_sessions) هرگز خوانده نمی‌شد
  ۳) انتخاب قالب برای هر رویداد ممکن نبود
  ۴) روش ثبت حضور قابل تغییر نبود · غایبان فهرست نداشتند ·
     صفحه‌بندی حاضرین کار نمی‌کرد · تأخیر/غیبت موجه بی‌استفاده
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora22_")
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
FILES = []


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
    FILES.append({"m": method, "cid": cid, "f": str(f), "cap": caption})
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
bale_api.answer_callback = lambda *a, **k: {"ok": True}

import config  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import certgen as CG  # noqa: E402
import certissue as CI  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import main as M  # noqa: E402

for mod in (EV, AT, CG, CI, M):
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


def to(u):
    return [s["p"].get("text") or "" for s in SENT
            if s["p"].get("cid") == u]


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1,
                        "chat": {"id": uid, "type": "private"}}}


print("=" * 62)
print("🧪 تست فاز ۲۲ — حضور و غیاب · مرکز صدور گواهینامه")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PM.init_permission_tables()
CG.init_cert_tables()
database.seed_default_settings()

S = 100000001
U1, U2, U3, U4 = 2210001, 2210002, 2210003, 2210004

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000",
                      "phone")
auth.ensure_super_admin(S)
for i, u in enumerate((U1, U2, U3, U4)):
    auth.create_auth_user({"id": u, "first_name": f"کاربر{i+1}",
                           "last_name": "آزمون"},
                          f"0912111000{i}", "phone")
    database.db_execute("UPDATE users SET national_id=? "
                        "WHERE bale_user_id=?", (f"001024716{i}", u))

EID = database.db_execute("""INSERT INTO events
    (title, event_type, location_type, start_date, status, is_paid,
     has_attendance, has_certificate, capacity, points_reward,
     duration_minutes, created_by)
    VALUES ('دوره مهارت زندگی','workshop','physical','1404/07/01',
            'published',0,1,1,50,10,180,?)""", (S,))
for u in (U1, U2, U3, U4):
    database.db_execute("""INSERT INTO event_registrations
        (event_id, user_id, bale_user_id, status, ticket_code)
        VALUES (?,?,?,'confirmed',?)""",
        (EID, auth.get_user(u)["id"], u, f"TK{u}"))


# ═══════════ ۱) ✋ جلسه — روش ثبت ═══════════
print("\n[۱] ✋ روش ثبت حضور — قابل تغییر شد")

SENT.clear()
M.handle_callback(cb(S, f"att_new_{EID}"))
SID = database.db_scalar("SELECT id FROM attendance_sessions "
                         "WHERE event_id=? ORDER BY id DESC LIMIT 1",
                         (EID,))
check("جلسه ساخته شد", bool(SID))

SENT.clear()
M.handle_callback(cb(S, f"att_meth_{SID}"))
check("🔀 صفحه روش ثبت باز شد", "روش ثبت حضور" in last(), last()[:60])
for k in AT.ATT_METHODS:
    check(f"روش «{AT.ATT_METHODS[k]['name']}» دکمه دارد",
          f"att_setm_{SID}_{k}" in allcb())

SENT.clear()
M.handle_callback(cb(S, f"att_setm_{SID}_ticket"))
_m = database.db_execute("SELECT method FROM attendance_sessions "
                         "WHERE id=?", (SID,), fetch="one")
check("🔴 روش واقعاً عوض شد (قبلاً ممکن نبود)",
      _m["method"] == "ticket", str(_m))

M.handle_callback(cb(S, f"att_setm_{SID}_code"))
check("برگشت به کد جلسه",
      database.db_execute("SELECT method FROM attendance_sessions "
                          "WHERE id=?", (SID,), fetch="one")["method"]
      == "code")


# ═══════════ ۲) ⚙️ تنظیمات جلسه ═══════════
print("\n[۲] ⚙️ تنظیمات کامل جلسه")

SENT.clear()
M.handle_callback(cb(S, f"att_set_{SID}"))
check("صفحه تنظیمات باز شد", "تنظیمات جلسه" in last())
for key, _i, name, _k, _h in AT.SESSION_FIELDS:
    check(f"فیلد «{name}» دکمه دارد", f"att_fld_{SID}_{key}" in allcb())

SENT.clear()
M.handle_callback(cb(S, f"att_fld_{SID}_title"))
check("ورود عنوان باز شد", "عنوان جلسه" in last())
M.process_message(msg(S, "جلسه اول — آشنایی"))
_s = database.db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                         (SID,), fetch="one")
check("📝 عنوان ذخیره شد", _s["title"] == "جلسه اول — آشنایی",
      str(_s["title"]))

M.handle_callback(cb(S, f"att_fld_{SID}_late_after"))
M.process_message(msg(S, "۱۵"))
_s = database.db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                         (SID,), fetch="one")
check("⏰ عدد فارسی درست خوانده شد", _s["late_after"] == 15,
      str(_s["late_after"]))

M.handle_callback(cb(S, f"att_fld_{SID}_points"))
M.process_message(msg(S, "25"))
check("🏆 امتیاز ذخیره شد",
      database.db_execute("SELECT points FROM attendance_sessions "
                          "WHERE id=?", (SID,), fetch="one")["points"] == 25)

# ستون‌های جدید واقعاً در جدول هستند
_cols = [r["name"] for r in database.db_execute(
    "PRAGMA table_info(attendance_sessions)", fetch="all")]
for c in ("session_date", "start_time", "late_after"):
    check(f"ستون «{c}» به جدول اضافه شد", c in _cols)


# ═══════════ ۳) 📍 موقعیت محل جلسه ═══════════
print("\n[۳] 📍 ثبت موقعیت محل")

SENT.clear()
M.handle_callback(cb(S, f"att_loc_{SID}"))
check("درخواست موقعیت", "موقعیت" in last())
check("state درست", auth.get_state_name(S) == AT.STATE_ATT_SETLOC)
M.process_update({"update_id": 9, "message": {
    "message_id": 3, "from": {"id": S},
    "chat": {"id": S, "type": "private"},
    "location": {"latitude": 35.7, "longitude": 51.4}}})
_s = database.db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                         (SID,), fetch="one")
check("📍 مختصات ذخیره شد", _s["lat"] and abs(_s["lat"] - 35.7) < 0.01)
check("🔀 روش خودکار روی موقعیت رفت", _s["method"] == "location")
database.db_execute("UPDATE attendance_sessions SET method='code' "
                    "WHERE id=?", (SID,))


# ═══════════ ۴) ✍️ چهار وضعیت حضور ═══════════
print("\n[۴] ✍️ حاضر · تأخیر · غیبت موجه · غایب")

check("چهار وضعیت تعریف شده", len(AT.ATT_STATUS_FA) == 4)
for k in ("present", "late", "excused", "absent"):
    check(f"وضعیت «{k}» آیکن دارد", k in AT.ATT_ICONS)

M.handle_callback(cb(S, f"attm_{SID}_{U1}_0"))
check("✅ حضور دستی ثبت شد",
      bool(database.db_execute(
          "SELECT 1 FROM attendance_records WHERE session_id=? "
          "AND bale_user_id=?", (SID, U1), fetch="one")))

SENT.clear()
M.handle_callback(cb(S, f"attst_{SID}_{U1}_0"))
check("🔀 کارت تغییر وضعیت باز شد", "وضعیت فعلی" in last(), last()[:60])
for k in AT.ATT_STATUS_FA:
    check(f"دکمه «{AT.ATT_STATUS_FA[k]}» هست",
          f"attsv_{SID}_{U1}_{k}_0" in allcb())

M.handle_callback(cb(S, f"attsv_{SID}_{U1}_late_0"))
_r = database.db_execute("SELECT status FROM attendance_records "
                         "WHERE session_id=? AND bale_user_id=?",
                         (SID, U1), fetch="one")
check("🔴 تأخیر ثبت شد (قبلاً ممکن نبود)", _r["status"] == "late",
      str(_r))

M.handle_callback(cb(S, f"attsv_{SID}_{U2}_excused_0"))
_r2 = database.db_execute("SELECT status FROM attendance_records "
                          "WHERE session_id=? AND bale_user_id=?",
                          (SID, U2), fetch="one")
check("🔴 غیبت موجه ثبت شد", _r2["status"] == "excused", str(_r2))

M.handle_callback(cb(S, f"attsv_{SID}_{U2}_absent_0"))
check("غایب کردن رکورد را پاک می‌کند",
      not database.db_execute(
          "SELECT 1 FROM attendance_records WHERE session_id=? "
          "AND bale_user_id=?", (SID, U2), fetch="one"))


# ═══════════ ۵) 📊 آمار دقیق ═══════════
print("\n[۵] 📊 آمار جلسه")

M.handle_callback(cb(S, f"attsv_{SID}_{U2}_present_0"))
M.handle_callback(cb(S, f"attsv_{SID}_{U3}_excused_0"))
st = AT.session_stats(SID, EID)
check("آمار حاضر درست", st["present"] == 1, str(st))
check("آمار تأخیر درست", st["late"] == 1, str(st))
check("🔴 غیبت موجه شمرده می‌شود (قبلاً نه)", st["excused"] == 1,
      str(st))
check("غایب درست حساب شد", st["absent"] == 1, str(st))
check("کل ثبت‌نامی درست", st["total"] == 4, str(st))
check("نرخ حضور محاسبه شد", st["rate"] == 50, str(st))

SENT.clear()
M.handle_callback(cb(S, f"att_view_{SID}"))
_t = last()
check("کارت جلسه غیبت موجه را نشان می‌دهد", "غیبت موجه" in _t)
check("کارت جلسه نرخ حضور دارد", "نرخ حضور" in _t)
check("دکمه غایبان هست", f"att_abs_{SID}_0" in allcb())
check("دکمه تغییر روش هست", f"att_meth_{SID}" in allcb())


# ═══════════ ۶) ❌ فهرست غایبان ═══════════
print("\n[۶] ❌ غایبان — قابلیت جدید")

SENT.clear()
M.handle_callback(cb(S, f"att_abs_{SID}_0"))
check("فهرست غایبان باز شد", "غایبان" in last(), last()[:50])
check("کاربر۴ در غایبان هست", "کاربر4" in last(), last()[:200])
check("دکمه حاضر کردن سریع دارد",
      any(c.startswith(f"attm_{SID}_{U4}") for c in allcb()))
check("دکمه یادآوری دارد", f"att_remind_{SID}" in allcb())

SENT.clear()
M.handle_callback(cb(S, f"att_remind_{SID}"))
check("📣 یادآوری فرستاده شد", "یادآوری شد" in alltext(),
      last()[:60])
check("پیام به غایب رسید",
      any("یادآوری حضور" in t for t in to(U4)))
check("پیام به حاضرین نرفت",
      not any("یادآوری حضور" in t for t in to(U1)))


# ═══════════ ۷) 📄 صفحه‌بندی حاضرین ═══════════
print("\n[۷] 📄 صفحه‌بندی — باگ رفع شد")

_src = (ROOT / "attendance.py").read_text(encoding="utf-8")
check("🔴 show_who حالا OFFSET دارد",
      "OFFSET" in _src.split("def show_who")[1].split("def ")[0])
SENT.clear()
M.handle_callback(cb(S, f"att_who_{SID}_0"))
check("فهرست حاضرین باز شد", "حاضرین" in last())
check("آیکن وضعیت‌ها نمایش داده می‌شود",
      "⏰" in last() or "📄" in last())
check("روی نام می‌شود زد",
      any(c.startswith("attst_") for c in allcb()))


# ═══════════ ۸) ✅ حاضر کردن همه ═══════════
print("\n[۸] ✅ عملیات گروهی")

SENT.clear()
M.handle_callback(cb(S, f"att_all_{SID}"))
check("تأیید حاضر کردن همه", "حاضر کردن همه" in last())
M.handle_callback(cb(S, f"att_ally_{SID}"))
st2 = AT.session_stats(SID, EID)
check("✅ همه ثبت شدند", st2["absent"] == 0, str(st2))
check("وضعیت‌های قبلی دست‌نخورده ماند",
      st2["late"] == 1 and st2["excused"] == 1, str(st2))

SENT.clear()
M.handle_callback(cb(S, f"att_clr_{SID}"))
check("تأیید پاکسازی خواسته شد", "پاک" in last())


# ═══════════ ۹) 🎓 شرط دریافت گواهینامه ═══════════
print("\n[۹] 🎓 شرط دریافت — باگ ۲ رفع شد")

check("شش شرط تعریف شده", len(CI.CONDITIONS) == 6)
SENT.clear()
M.handle_callback(cb(S, f"ci_cond_{EID}"))
check("صفحه شرط باز شد", "شرط دریافت" in last())
for k in CI.CONDITIONS:
    check(f"شرط «{CI.CONDITIONS[k]['name']}» دکمه دارد",
          f"ci_setc_{EID}_{k}" in allcb())

M.handle_callback(cb(S, f"ci_setc_{EID}_registered"))
ok, no, ct = CI.eligible(EID)
check("📝 شرط ثبت‌نام: همه واجدند", len(ok) == 4, f"{len(ok)}")

M.handle_callback(cb(S, f"ci_setc_{EID}_all"))
ok, no, ct = CI.eligible(EID)
check("💯 شرط حضور کامل اعمال شد", len(ok) == 4, f"{len(ok)}/{ct}")

# یک نفر را غایب کن
M.handle_callback(cb(S, f"attsv_{SID}_{U4}_absent_0"))
ok, no, ct = CI.eligible(EID)
check("🔴 غایب واقعاً رد می‌شود (قبلاً نمی‌شد)",
      len(ok) == 3 and len(no) == 1, f"{len(ok)}/{len(no)}")
check("دلیل رد ذکر می‌شود", no and no[0].get("why"), str(no[:1]))

M.handle_callback(cb(S, f"ci_setc_{EID}_sessions"))
M.handle_callback(cb(S, f"ci_pset_{EID}_min_sessions"))
M.process_message(msg(S, "1"))
check("🔢 حداقل جلسه ذخیره شد", CI.min_sessions_of(EID) == 1,
      str(CI.min_sessions_of(EID)))

M.handle_callback(cb(S, f"ci_setc_{EID}_percent"))
M.handle_callback(cb(S, f"ci_pset_{EID}_min_percent"))
M.process_message(msg(S, "150"))
check("📊 درصد بالای ۱۰۰ محدود شد", CI.min_percent_of(EID) == 100,
      str(CI.min_percent_of(EID)))

# انتخاب دستی
M.handle_callback(cb(S, f"ci_setc_{EID}_manual"))
SENT.clear()
M.handle_callback(cb(S, f"ci_pick_{EID}_0"))
check("👤 صفحه انتخاب دستی باز شد", "انتخاب دستی" in last())
M.handle_callback(cb(S, f"ci_tog_{EID}_{U1}_0"))
ok, no, ct = CI.eligible(EID)
check("انتخاب دستی فقط همان نفر", len(ok) == 1, str(len(ok)))
M.handle_callback(cb(S, f"ci_setc_{EID}_registered"))


# ═══════════ ۹.۵) 📄 غیبت موجه = حضور ═══════════
print("\n[۹.۵] 📄 غیبت موجه به‌جای حضور")

check("پیش‌فرض روشن است", CI.excused_counts() is True)
M.handle_callback(cb(S, f"ci_setc_{EID}_all"))
M.handle_callback(cb(S, f"attsv_{SID}_{U4}_present_0"))
M.handle_callback(cb(S, f"attsv_{SID}_{U3}_excused_0"))
ok, no, _c = CI.eligible(EID)
check("📄 غیبت موجه مثل حضور حساب می‌شود", len(ok) == 4,
      f"{len(ok)}")

SENT.clear()
M.handle_callback(cb(S, f"ci_exc_{EID}"))
check("🔀 خاموش شد", CI.excused_counts() is False)
ok, no, _c = CI.eligible(EID)
check("🔴 حالا غیبت موجه رد می‌شود", len(ok) == 3, f"{len(ok)}")
M.handle_callback(cb(S, f"ci_exc_{EID}"))
check("♻️ دوباره روشن شد", CI.excused_counts() is True)
M.handle_callback(cb(S, f"ci_setc_{EID}_registered"))


# ═══════════ ۱۰) 🛡️ رویداد بدون جلسه ═══════════
print("\n[۱۰] 🛡️ رویداد بدون جلسه نباید قفل شود")

E2 = database.db_execute("""INSERT INTO events
    (title, event_type, status, capacity, created_by, has_certificate,
     start_date) VALUES ('همایش تک‌جلسه','seminar','published',30,?,1,
     '1404/08/01')""", (S,))
database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'attended')""", (E2, auth.get_user(U1)["id"], U1))
database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'confirmed')""", (E2, auth.get_user(U2)["id"], U2))

check("رویداد بدون جلسه: صفر جلسه", CI.sessions_count(E2) == 0)
ok2, no2, _c = CI.eligible(E2)
check("🔴 پیش‌فرض همه را رد نمی‌کند", len(ok2) == 2, f"{len(ok2)}")

CI.cfg_set(E2, "condition", "attended")
ok2, no2, _c = CI.eligible(E2)
check("🔴 با شرط حضور، به attended برمی‌گردد (قفل نمی‌شود)",
      len(ok2) == 1, f"{len(ok2)}/{len(no2)}")
CI.cfg_set(E2, "condition", "registered")


# ═══════════ ۱۱) 📄 انتخاب قالب ═══════════
print("\n[۱۱] 📄 انتخاب قالب — باگ ۳ رفع شد")

_tpl = Path(TMP) / "tpl.docx"
try:
    import docx as _dx
    d = _dx.Document()
    d.add_paragraph("گواهی می‌شود {نام} با کدملی {کدملی}")
    d.add_paragraph("در دوره {رویداد} شرکت نمود. شماره: {شماره}")
    d.save(str(_tpl))
    _has_docx = True
except ImportError:
    _has_docx = False

if _has_docx:
    T1 = database.db_execute("""INSERT INTO cert_templates
        (name, kind, file_path, placeholders, is_active, is_default,
         created_by) VALUES ('قالب الف','docx',?,'[]',1,1,?)""",
        (str(_tpl), S))
    T2 = database.db_execute("""INSERT INTO cert_templates
        (name, kind, file_path, placeholders, is_active, is_default,
         created_by) VALUES ('قالب ب','docx',?,'[]',1,0,?)""",
        (str(_tpl), S))

    SENT.clear()
    M.handle_callback(cb(S, f"ci_tpl_{EID}"))
    check("صفحه انتخاب قالب باز شد", "قالب گواهینامه" in last())
    check("هر دو قالب دکمه دارند",
          f"ci_setpl_{EID}_{T1}" in allcb()
          and f"ci_setpl_{EID}_{T2}" in allcb())

    check("پیش‌فرض قالب پیش‌فرض ربات است",
          CI.template_of(EID)["id"] == T1)
    M.handle_callback(cb(S, f"ci_setpl_{EID}_{T2}"))
    check("🔴 قالب اختصاصی رویداد انتخاب شد (قبلاً ممکن نبود)",
          CI.template_of(EID)["id"] == T2,
          str(CI.template_of(EID)["id"]))
    check("رویداد دیگر همچنان پیش‌فرض دارد",
          CI.template_of(E2)["id"] == T1)

    M.handle_callback(cb(S, f"ci_setpl_{EID}_0"))
    check("برگشت به پیش‌فرض کار می‌کند",
          CI.template_of(EID)["id"] == T1)
    M.handle_callback(cb(S, f"ci_setpl_{EID}_{T2}"))
else:
    check("⚠️ python-docx نیست — تست قالب رد شد", True)


# ═══════════ ۱۲) ✏️ پارامترها ═══════════
print("\n[۱۲] ✏️ تغییر پارامترها — باگ ۴ رفع شد")

SENT.clear()
M.handle_callback(cb(S, f"ci_par_{EID}"))
check("صفحه پارامترها باز شد", "پارامترهای گواهینامه" in last())
check("پارامترهای کافی دارد", len(CI.EVENT_PARAMS) >= 10,
      str(len(CI.EVENT_PARAMS)))
for key, _i, name, _h in CI.EVENT_PARAMS[:4]:
    check(f"پارامتر «{name}» دکمه دارد",
          f"ci_pset_{EID}_{key}" in allcb())

M.handle_callback(cb(S, f"ci_pset_{EID}_teacher"))
check("ورود مقدار باز شد", "استاد" in last())
M.process_message(msg(S, "دکتر رضایی"))
check("✏️ پارامتر ذخیره شد",
      (CI.get_cfg(EID).get("params") or {}).get("teacher") == "دکتر رضایی",
      str(CI.get_cfg(EID).get("params")))

mp = CI.build_for(EID, U1, "T-1")
check("🔴 پارامتر دستی در گواهینامه اعمال می‌شود",
      mp.get("teacher") == "دکتر رضایی", str(mp.get("teacher")))
check("مقدار خودکار هم پر است", mp.get("event") == "دوره مهارت زندگی")
# 🔢 فاز ۲۷ — اعداد گواهینامه فارسی می‌شوند
check("ساعت آموزشی خودکار محاسبه شد",
      str(mp.get("hours")) in ("3", "۳"),
      str(mp.get("hours")))
check("نام کاربر درست است",
      "کاربر1" in str(mp.get("name"))
      or "کاربر۱" in str(mp.get("name")), str(mp.get("name")))
check("کد ملی پر شد",
      mp.get("national_id") in ("0010247160", "۰۰۱۰۲۴۷۱۶۰"),
      str(mp.get("national_id")))

# پارامتر دستی بر خودکار اولویت دارد
M.handle_callback(cb(S, f"ci_pset_{EID}_hours"))
M.process_message(msg(S, "24"))
mp = CI.build_for(EID, U1, "T-2")
check("🔴 دستی بر خودکار اولویت دارد",
      str(mp.get("hours")) in ("24", "۲۴"),
      str(mp.get("hours")))

M.handle_callback(cb(S, f"ci_pset_{EID}_hours"))
M.process_message(msg(S, "-"))
mp = CI.build_for(EID, U1, "T-3")
check("با «-» به خودکار برمی‌گردد",
      str(mp.get("hours")) in ("3", "۳"),
      str(mp.get("hours")))

M.handle_callback(cb(S, f"ci_pclr_{EID}"))
check("🧹 پاک کردن همه کار کرد",
      not (CI.get_cfg(EID).get("params") or {}))
M.handle_callback(cb(S, f"ci_pset_{EID}_teacher"))
M.process_message(msg(S, "دکتر رضایی"))


# ═══════════ ۱۳) 🎓 صدور واقعی با فایل ═══════════
print("\n[۱۳] 🎓 صدور با فایل — باگ ۱ رفع شد")

database.db_execute("DELETE FROM certificates WHERE event_id=?", (EID,))
SENT.clear()
FILES.clear()
cert, err = CI.issue_one(EID, U1, S)
check("🎓 گواهینامه صادر شد", bool(cert), str(err))
check("شماره سریال دارد", cert and cert.get("serial"))
if _has_docx:
    check("🔴 به قالب رویداد وصل است", cert.get("template_id") == T2,
          str(cert.get("template_id")))
    check("🔴 فایل ورد ساخته شد",
          cert.get("docx_path") and Path(cert["docx_path"]).exists())
    check("🔴 فایل واقعی برای کاربر فرستاده شد (باگ اصلی!)",
          any(f["cid"] == U1 and f["m"] in ("sendPhoto", "sendDocument")
              for f in FILES), str(FILES[:2]))
check("پیام تبریک هم رفت",
      any("گواهینامه" in t for t in to(U1)))

# محتوای فایل ورد را بررسی کن
if _has_docx and cert.get("docx_path"):
    _d = _dx.Document(cert["docx_path"])
    body = "\n".join(p.text for p in _d.paragraphs)
    check("🔴 نام واقعاً جایگزین شد",
          "کاربر1" in body or "کاربر۱" in body, body[:100])
    check("🔴 کدملی جایگزین شد",
          "0010247160" in body or "۰۰۱۰۲۴۷۱۶۰" in body, body[:100])
    check("نام رویداد جایگزین شد", "دوره مهارت زندگی" in body)
    check("جای خالی باقی نماند", "{" not in body, body[:100])

# تکراری صادر نمی‌شود
c2, _e = CI.issue_one(EID, U1, S)
check("تکراری صادر نمی‌شود", c2["id"] == cert["id"])
n_all = database.db_scalar("SELECT COUNT(*) FROM certificates "
                           "WHERE event_id=?", (EID,))
check("فقط یک رکورد", n_all == 1, str(n_all))


# ═══════════ ۱۴) 👁️ پیش‌نمایش ═══════════
print("\n[۱۴] 👁️ پیش‌نمایش قبل از صدور")

SENT.clear()
FILES.clear()
_before = database.db_scalar("SELECT COUNT(*) FROM certificates")
M.handle_callback(cb(S, f"ci_prev_{EID}"))
check("پیش‌نمایش اجرا شد", "پیش‌نمایش" in alltext())
check("🔴 پیش‌نمایش رکورد نمی‌سازد",
      database.db_scalar("SELECT COUNT(*) FROM certificates") == _before)


# ═══════════ ۱۵) 🎓 صدور گروهی ═══════════
print("\n[۱۵] 🎓 صدور گروهی کامل")

SENT.clear()
M.handle_callback(cb(S, f"cert_bulk_{EID}"))
_t = last()
check("مرکز صدور باز شد", "صدور" in _t and "گواهینامه" in _t)
check("قالب را نشان می‌دهد", "قالب" in _t)
check("شرط را نشان می‌دهد", "شرط" in _t)
check("همه درها هست",
      f"ci_tpl_{EID}" in allcb() and f"ci_cond_{EID}" in allcb()
      and f"ci_par_{EID}" in allcb() and f"ci_prev_{EID}" in allcb())

SENT.clear()
M.handle_callback(cb(S, f"ci_run_{EID}"))
check("صفحه تأیید باز شد", "تأیید صدور" in last() or "صدور" in last())

SENT.clear()
FILES.clear()
M.handle_callback(cb(S, f"ci_go_{EID}"))
check("✅ صدور گروهی تمام شد", "تمام شد" in alltext())
n_all = database.db_scalar("SELECT COUNT(*) FROM certificates "
                           "WHERE event_id=?", (EID,))
check("🔴 برای همه صادر شد", n_all == 4, str(n_all))
if _has_docx:
    check("🔴 به همه فایل رفت (باگ اصلی رفع شد)",
          len([f for f in FILES if f["m"] in ("sendPhoto",
                                              "sendDocument")]) >= 3,
          str(len(FILES)))
check("گواهینامه‌ها قالب دارند",
      database.db_scalar("SELECT COUNT(*) FROM certificates "
                         "WHERE event_id=? AND template_id IS NOT NULL",
                         (EID,)) >= 1 or not _has_docx)


# ═══════════ ۱۶) 📜 مدیریت صادرشده‌ها ═══════════
print("\n[۱۶] 📜 مدیریت گواهینامه‌ها")

SENT.clear()
M.handle_callback(cb(S, f"ci_done_{EID}_0"))
check("فهرست صادرشده‌ها باز شد", "صادرشده" in last())

SENT.clear()
M.handle_callback(cb(S, f"ci_one_{EID}_{U1}"))
check("کارت فرد باز شد", "کاربر1" in last())
check("حضور را نشان می‌دهد", "حضور" in last())
check("دکمه ابطال دارد", f"ci_rev_{EID}_{U1}" in allcb())
check("دکمه ارسال دوباره دارد", f"ci_resend_{EID}_{U1}" in allcb())

M.handle_callback(cb(S, f"ci_rev_{EID}_{U1}"))
check("🚫 ابطال شد",
      database.db_execute("SELECT revoked FROM certificates "
                          "WHERE event_id=? AND bale_user_id=?",
                          (EID, U1), fetch="one")["revoked"] == 1)
M.handle_callback(cb(S, f"ci_unrev_{EID}_{U1}"))
check("♻️ برگشت از ابطال",
      database.db_execute("SELECT revoked FROM certificates "
                          "WHERE event_id=? AND bale_user_id=?",
                          (EID, U1), fetch="one")["revoked"] == 0)

SENT.clear()
FILES.clear()
M.handle_callback(cb(S, f"ci_resend_{EID}_{U1}"))
check("📤 ارسال دوباره کار کرد", "فرستاده شد" in alltext())

SENT.clear()
M.handle_callback(cb(S, f"ci_resall_{EID}"))
check("📤 ارسال به همه کار کرد", "فرستاده شد" in alltext())


# ═══════════ ۱۷) 📊 آمار ═══════════
print("\n[۱۷] 📊 آمار گواهینامه")

SENT.clear()
M.handle_callback(cb(S, f"ci_stat_{EID}"))
_t = last()
check("صفحه آمار باز شد", "آمار گواهینامه" in _t)
check("تعداد صادرشده", "صادرشده" in _t)
check("توزیع حضور", "توزیع حضور" in _t)

SENT.clear()
M.handle_callback(cb(S, f"ci_ok_{EID}_0"))
check("فهرست واجدین باز شد", "واجدین شرایط" in last())


# ═══════════ ۱۸) 👤 کاربر ═══════════
print("\n[۱۸] 👤 سمت کاربر")

database.db_execute("DELETE FROM certificates WHERE event_id=?", (E2,))
CI.cfg_set(E2, "condition", "attended")
SENT.clear()
FILES.clear()
_c = AT.issue_certificate(U2, U2, E2, target_uid=U2)
check("🔴 کاربر واجد شرایط نیست → رد می‌شود", _c is None)
check("پیام مهربان است",
      "واجد شرایط" in alltext() or "موفق باشید" in alltext(),
      last()[:80])

SENT.clear()
FILES.clear()
_c = AT.issue_certificate(U1, U1, E2, target_uid=U1)
check("✅ کاربر واجد شرایط گواهینامه گرفت", bool(_c))
if _has_docx:
    check("🔴 فایل واقعی به کاربر رسید",
          any(f["cid"] == U1 for f in FILES), str(FILES[:2]))

SENT.clear()
M.handle_callback(cb(U1, "u_my_certs"))
check("گواهینامه‌های من کار می‌کند", "گواهینامه" in last())


# ═══════════ ۱۹) 🔒 امنیت ═══════════
print("\n[۱۹] 🔒 دسترسی")

for d in (f"cert_bulk_{EID}", f"ci_tpl_{EID}", f"ci_cond_{EID}",
          f"ci_par_{EID}", f"ci_go_{EID}", f"ci_rev_{EID}_{U1}",
          f"att_meth_{SID}", f"att_set_{SID}", f"att_abs_{SID}_0",
          f"att_all_{SID}", f"attsv_{SID}_{U1}_present_0"):
    SENT.clear()
    M.handle_callback(cb(U2, d))
    check(f"🔒 کاربر عادی: {d[:22]}", "دسترسی" in last(), last()[:40])


# ═══════════ ۲۰) 🛡️ ورودی خراب ═══════════
print("\n[۲۰] 🛡️ ورودی‌های خراب")

for d in ("ci_tpl_abc", "ci_one_1_abc", "ci_setc_9_bad", "ci_go_99999",
          "att_setm_1_bad", "attsv_1_1_bad_0", "att_fld_1_nokey",
          f"ci_setpl_{EID}_99999", "ci_pset_1_nokey", "att_abs_x_0"):
    SENT.clear()
    try:
        M.handle_callback(cb(S, d))
        check(f"🛡️ «{d[:24]}» کرش نمی‌کند", True)
    except Exception as e:
        check(f"🛡️ «{d[:24]}» کرش نمی‌کند", False, str(e)[:70])

check("رویداد ناموجود کرش نمی‌کند",
      isinstance(CI.eligible(99999)[0], list))
check("cfg رویداد ناموجود خالی است", CI.get_cfg(99999) == {})
check("build_for با کاربر ناموجود کرش نمی‌کند",
      isinstance(CI.build_for(EID, 99999, "X"), dict))


# ═══════════ ۲۱) 🛡️ رگرسیون ═══════════
print("\n[۲۱] 🛡️ رگرسیون")

for a in ("session_method_changed", "attendance_status_set",
          "cert_bulk_issued", "cert_revoked", "attendance_reminded"):
    check(f"لاگ فارسی «{a}»", a in AL.ACTION_FA)

SENT.clear()
M.handle_callback(cb(S, f"att_list_{EID}"))
check("لیست جلسات سالم", "حضور و غیاب" in last())
check("دکمه گواهینامه در جلسات", f"cert_bulk_{EID}" in allcb())

SENT.clear()
M.handle_callback(cb(S, f"att_report_{EID}"))
check("کارنامه سالم", "کارنامه" in last())

SENT.clear()
M.handle_callback(cb(S, f"ev_view_{EID}"))
check("کارت رویداد سالم", "دوره مهارت زندگی" in last())
check("دکمه گواهینامه در رویداد", f"cert_bulk_{EID}" in allcb())

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("هاب قالب سالم", "گواهینامه" in last())

import guard as G  # noqa: E402
_f = G.check_new_features()
check("🛡️ همه قابلیت‌ها سالم", all(_f.values()),
      str([k for k, v in _f.items() if not v]))

check("📛 «گواهی حضور» نیامده",
      "گواهینامه حضور" not in
      (ROOT / "certissue.py").read_text(encoding="utf-8"))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۲ پاس شدند!")
