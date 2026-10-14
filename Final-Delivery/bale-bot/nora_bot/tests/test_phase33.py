#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 تست فاز ۳۳ — فرم رویدادی · نظرسنجی · جلسات خودکار · حضور آنلاین

سه درخواست کاربر:
  ۱. «فرم‌های اختصاصی رویدادها … وقتی انتشار میزنم همه کاربرا
      میتونن ببینن — اینو حل کن»
  ۲. «نظرسنجی بعد رویداد رو حرفه‌ای و کامل کن»
  ۳. «حضور و غیاب باید یه دور دیگه جلسه تعیین کنم تا کار کنه —
      اتوماتیک کن و امکانات آنلاین رو کامل کن»
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OK = 0
FAIL = 0
ERRORS = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        ERRORS.append(f"{label} {detail}")


def section(t):
    print(f"\n{'─' * 62}\n{t}\n{'─' * 62}")


import database
import forms as F
import survey as SV
import attendance_auto as AA


# ══════════════════════════════════════════════════════════
section("۱) 🎉 فرم رویدادی فقط برای شرکت‌کنندگان")
# ══════════════════════════════════════════════════════════
check("event_form_gate موجود", hasattr(F, "event_form_gate"))
check("EV_ACCESS موجود", hasattr(F, "EV_ACCESS"))
check("show_event_access موجود", hasattr(F, "show_event_access"))
check("۳ سطح دسترسی", len(F.EV_ACCESS) == 3, str(list(F.EV_ACCESS)))
for k in ("registered", "attended", "public"):
    check(f"سطح {k}", k in F.EV_ACCESS)

# ستون در schema
check("ستون event_access", "event_access" in F.FORMS_SCHEMA)
check("پیش‌فرض registered",
      "registered" in str(F.FORMS_SCHEMA.get("event_access", "")))

F.init_form_tables() if hasattr(F, "init_form_tables") else None
import events as EV
EV.init_event_tables()
import attendance as ATT
ATT.init_attendance_tables()

EVID = 993301
UID_IN, UID_OUT = 8801, 8802
database.db_execute("DELETE FROM event_registrations WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM attendance_records WHERE event_id=?",
                    (EVID,))
database.db_execute(
    "INSERT INTO event_registrations (event_id, bale_user_id, status, "
    "amount_paid) VALUES (?,?,'confirmed',50000)", (EVID, UID_IN))

# فرم وابسته به رویداد
fake = {"id": 99331, "status": "active", "event_id": EVID,
        "event_access": "registered", "form_type": "survey"}

ok, why = F.event_form_gate(fake, UID_IN)
check("ثبت‌نام‌شده اجازه دارد", ok, why)
ok2, why2 = F.event_form_gate(fake, UID_OUT)
check("🔴 غیرثبت‌نامی رد شد", not ok2, f"→ {ok2}")
check("دلیل درست", why2 == "ev_not_registered", why2)

# حالت attended
fake["event_access"] = "attended"
ok3, why3 = F.event_form_gate(fake, UID_IN)
check("بدون حضور رد شد", not ok3 and why3 == "ev_not_attended", why3)
database.db_execute(
    "INSERT INTO attendance_records (session_id, event_id, "
    "bale_user_id, status) VALUES (?,?,?,'present')",
    (1, EVID, UID_IN))
ok4, why4 = F.event_form_gate(fake, UID_IN)
check("با حضور اجازه دارد", ok4, why4)

# حالت public
fake["event_access"] = "public"
ok5, _ = F.event_form_gate(fake, UID_OUT)
check("public همه را راه می‌دهد", ok5)

# فرم بدون رویداد نباید محدود شود
ok6, _ = F.event_form_gate({"id": 1}, UID_OUT)
check("فرم بدون رویداد آزاد", ok6)

# 🔗 اتصال به form_gate
src = Path("forms.py").read_text(encoding="utf-8")
check("form_gate صدا می‌زند", "event_form_gate(form, uid)" in src)
ff = Path("form_fill.py").read_text(encoding="utf-8")
check("پیام مهربان", "_event_only_message" in ff)
check("دکمهٔ رویداد", 'uev_' in ff)

database.db_execute("DELETE FROM event_registrations WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM attendance_records WHERE event_id=?",
                    (EVID,))


# ══════════════════════════════════════════════════════════
section("۲) ⏰ جلسات خودکار")
# ══════════════════════════════════════════════════════════
AA.init_tables()
for fn in ["plan_sessions", "ensure_sessions", "sync_on_enable",
           "_jalali_add_days"]:
    check(f"AA.{fn}", hasattr(AA, fn))

# 📅 تقویم شمسی
cases = [
    ("1404/07/29", 7, "1404/08/06"),
    ("1404/06/31", 1, "1404/07/01"),      # مرز ۳۱ روزه
    ("1404/12/29", 1, "1405/01/01"),      # سال غیرکبیسه
    ("1403/12/29", 1, "1403/12/30"),      # سال کبیسه
    ("۱۴۰۴/۰۷/۲۹", 14, "1404/08/13"),     # ارقام فارسی
]
for d, n, want in cases:
    got = AA._jalali_add_days(d, n)
    check(f"تاریخ {d}+{n}", got == want, f"{got} ≠ {want}")
check("تاریخ خالی امن", AA._jalali_add_days("", 7) == "")
check("تاریخ خراب امن", AA._jalali_add_days("abc", 7) == "")

# نقشهٔ جلسات
plan = AA.plan_sessions({"sessions_count": 4, "start_date": "1404/07/01",
                         "start_time": "18:00", "location_type": "online"})
check("۴ جلسه برنامه‌ریزی شد", len(plan) == 4, str(len(plan)))
check("شمارهٔ جلسه درست", [p["session_no"] for p in plan] == [1, 2, 3, 4])
check("جلسهٔ اول باز", plan[0]["is_open"] == 1)
check("بقیه بسته", all(p["is_open"] == 0 for p in plan[1:]))
check("تاریخ‌ها متفاوت",
      len({p["session_date"] for p in plan}) == 4,
      str([p["session_date"] for p in plan]))
check("فاصلهٔ هفتگی", plan[1]["session_date"] == "1404/07/08",
      plan[1]["session_date"])
check("ساعت منتقل شد", plan[0]["start_time"] == "18:00")

# تک‌جلسه‌ای
one = AA.plan_sessions({"sessions_count": 1, "title": "همایش",
                        "start_date": "1404/08/01"})
check("تک‌جلسه‌ای", len(one) == 1)
check("عنوان از رویداد", "همایش" in one[0]["title"], one[0]["title"])

# sessions_count صفر یا منفی
z = AA.plan_sessions({"sessions_count": 0})
check("صفر → حداقل ۱ جلسه", len(z) == 1)

# ساخت واقعی
database.db_execute("DELETE FROM attendance_sessions WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM events WHERE id=?", (EVID,))
database.db_execute(
    "INSERT INTO events (id,title,event_type,status,has_attendance,"
    "sessions_count,start_date,start_time,location_type,created_by) "
    "VALUES (?,?,?,?,?,?,?,?,?,?)",
    (EVID, "کارگاه تست", "workshop", "published", 1, 3,
     "1404/07/01", "17:30", "online", 1))

database.db_execute("DELETE FROM attendance_sessions WHERE event_id=?",
                    (EVID,))
made, why = AA.ensure_sessions(EVID)
check("۳ جلسه ساخته شد", made == 3, f"{made} — {why}")
rows = database.db_execute(
    "SELECT * FROM attendance_sessions WHERE event_id=? "
    "ORDER BY session_no", (EVID,), fetch="all") or []
check("در دیتابیس هست", len(rows) == 3)
check("کد جلسه دارند", all(r.get("session_code") for r in rows))
check("کدها ساخته شدند",
      all(len(str(r["session_code"] or "")) >= 4 for r in rows),
      str([r["session_code"] for r in rows]))
check("روش آنلاین", all(r.get("method") for r in rows))

# دوباره نسازد
made2, _ = AA.ensure_sessions(EVID)
check("🔴 دوباره نمی‌سازد", made2 == 0, f"{made2}")

# رویداد بدون حضور
database.db_execute("UPDATE events SET has_attendance=0 WHERE id=?",
                    (EVID,))
made3, why3 = AA.ensure_sessions(EVID, force=True)
check("بدون حضور نمی‌سازد", made3 == 0, why3)
database.db_execute("UPDATE events SET has_attendance=1 WHERE id=?",
                    (EVID,))


# ══════════════════════════════════════════════════════════
section("۳) 🌐 حضور و غیاب آنلاین")
# ══════════════════════════════════════════════════════════
check("۶ روش آنلاین", len(AA.ONLINE_METHODS) == 6,
      str(list(AA.ONLINE_METHODS)))
for k in ("code", "onelink", "dwell", "rollcall", "rotating", "manual"):
    check(f"روش {k}", k in AA.ONLINE_METHODS)

SID = rows[0]["id"] if rows else None
if SID:
    # 🔐 رمز پویا
    c1, left = AA.rotating_code(SID)
    check("کد پویا ۶ رقمی", len(c1) == 6 and c1.isdigit(), c1)
    check("زمان باقی مثبت", left > 0)
    check("کد درست پذیرفته شد", AA.check_rotating(SID, c1))
    check("کد غلط رد شد", not AA.check_rotating(SID, "000000"))
    c2, _ = AA.rotating_code(SID)
    check("کد پایدار در بازه", c1 == c2)
    c3, _ = AA.rotating_code(SID + 1)
    check("کد هر جلسه جدا", c1 != c3)

    # 🔗 توکن یک‌بارمصرف
    tok = AA.issue_token(SID, UID_IN)
    check("توکن ساخته شد", bool(tok) and len(tok) >= 6, str(tok))
    tok2 = AA.issue_token(SID, UID_IN)
    check("توکن تکراری نمی‌سازد", tok == tok2)
    lnk = AA.token_link(tok)
    check("لینک شامل at_", f"at_{tok}" in lnk, lnk)

    ok, msg = AA.redeem_token(tok, UID_OUT)
    check("🔴 توکن دیگری رد شد", not ok, msg)
    ok, msg = AA.redeem_token(tok, UID_IN)
    check("توکن مصرف شد", ok, msg)
    ok, msg = AA.redeem_token(tok, UID_IN)
    check("توکن دوباره‌مصرف رد شد", not ok and "قبلاً" in msg, msg)
    ok, msg = AA.redeem_token("nonexistent", UID_IN)
    check("توکن نامعتبر رد شد", not ok)

    # ✅ حضور ثبت شد؟
    n = database.db_scalar(
        "SELECT COUNT(*) FROM attendance_records WHERE session_id=? "
        "AND bale_user_id=?", (SID, UID_IN))
    check("حضور ثبت شد", n >= 1, str(n))

    # ⏱️ ماندگاری
    database.db_execute("DELETE FROM att_presence WHERE session_id=?",
                        (SID,))
    ok, msg = AA.join(SID, UID_OUT)
    check("ورود ثبت شد", ok, msg)
    ok2, msg2 = AA.join(SID, UID_OUT)
    check("ورود دوباره پیام می‌دهد", ok2 and "قبل" in msg2, msg2)
    sec = AA.total_seconds(SID, UID_OUT)
    check("ثانیه شمرده می‌شود", sec >= 0)
    ok3, msg3 = AA.leave(SID, UID_OUT)
    check("خروج ثبت شد (کم‌تر از حد)", not ok3, msg3)
    ok4, _ = AA.leave(SID, UID_OUT)
    check("خروج بدون ورود رد شد", not ok4)

    # 🙋 فراخوان
    st = database.db_execute(
        "SELECT * FROM attendance_sessions WHERE id=?", (SID,),
        fetch="one")
    ok, msg = AA.mark_present(st, 8899, method="manual")
    check("ثبت دستی حضور", ok, msg)
    ok2, msg2 = AA.mark_present(st, 8899)
    check("حضور تکراری رد شد", not ok2 and "قبلاً" in msg2, msg2)

check("init_tables جدول ساخت", bool(database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND "
    "name='att_tokens'", fetch="one")))
for t in ("att_rollcalls", "att_rollcall_answers", "att_presence"):
    check(f"جدول {t}", bool(database.db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (t,), fetch="one")))


# ══════════════════════════════════════════════════════════
section("۴) 📊 نظرسنجی حرفه‌ای")
# ══════════════════════════════════════════════════════════
SV.init_tables()
for fn in ["due", "send_survey", "remind", "mark_answered",
           "on_form_submit", "stats", "analyze", "audience",
           "run_due", "run_reminders", "_nps", "bar"]:
    check(f"SV.{fn}", hasattr(SV, fn))

check("۴ زمان ارسال", len(SV.SEND_DELAY) == 4)
check("۳ نوع مخاطب", len(SV.AUDIENCE) == 3)

# NPS
check("NPS همه مروج", SV._nps([9, 10, 10, 9]) == 100)
check("NPS همه منتقد", SV._nps([1, 2, 3]) == -100)
check("NPS متعادل", SV._nps([10, 1]) == 0)
check("NPS خالی امن", SV._nps([]) == 0)
check("NPS خنثی‌ها", SV._nps([7, 8, 8]) == 0)

# نوار
check("bar کامل", SV.bar(10, 10) == "▓" * 10)
check("bar خالی", SV.bar(0, 10) == "░" * 10)
check("bar تقسیم بر صفر", SV.bar(5, 0) == "░" * 10)

# مخاطبان
database.db_execute("DELETE FROM event_registrations WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM survey_sends WHERE event_id=?", (EVID,))
for u, amt in ((7701, 50000), (7702, 0), (7703, 50000)):
    database.db_execute(
        "INSERT INTO event_registrations (event_id, bale_user_id, "
        "status, amount_paid) VALUES (?,?,'confirmed',?)",
        (EVID, u, amt))
database.db_execute("DELETE FROM attendance_records WHERE event_id=?",
                    (EVID,))
database.db_execute(
    "INSERT INTO attendance_records (session_id, event_id, "
    "bale_user_id, status) VALUES (?,?,?,'present')",
    (SID or 1, EVID, 7701))

check("مخاطب ثبت‌نامی", len(SV.audience(EVID, "registered")) == 3,
      str(SV.audience(EVID, "registered")))
check("مخاطب پرداخت‌کرده", len(SV.audience(EVID, "paid")) == 2)
check("مخاطب حاضر", len(SV.audience(EVID, "attended")) == 1)

# شرط ارسال
database.db_execute(
    "UPDATE events SET survey_enabled=1, survey_form_id=999331 "
    "WHERE id=?", (EVID,))
ok, why = SV.due(EVID)
check("رویداد ناتمام رد شد", not ok and "تمام نشده" in why, why)
database.db_execute("UPDATE events SET status='finished' WHERE id=?",
                    (EVID,))
database.db_execute("UPDATE events SET survey_form_id=NULL WHERE id=?",
                    (EVID,))
ok, why = SV.due(EVID)
check("بدون فرم رد شد", not ok and "فرم" in why, why)

# آمار خالی
st = SV.stats(EVID)
check("آمار خالی امن", st["sent"] == 0 and st["rate"] == 0)

# تحلیل بدون فرم
check("تحلیل بدون فرم امن", SV.analyze(EVID) == [])

# پاکسازی
database.db_execute("DELETE FROM event_registrations WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM attendance_records WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM attendance_sessions WHERE event_id=?",
                    (EVID,))
database.db_execute("DELETE FROM events WHERE id=?", (EVID,))
database.db_execute("DELETE FROM survey_sends WHERE event_id=?", (EVID,))


# ══════════════════════════════════════════════════════════
section("۵) روتر و اتصال‌ها")
# ══════════════════════════════════════════════════════════
mn = Path("main.py").read_text(encoding="utf-8")
check("import attendance_auto", "import attendance_auto" in mn)
check("import survey", "import survey as sv_mod" in mn)
check("init جلسات آنلاین", "aa_mod.init_tables()" in mn)
check("init نظرسنجی", "sv_mod.init_tables()" in mn)
check("deep-link at_", 'param.startswith("at_")' in mn)
check("cron نظرسنجی", "sv_mod.run_due()" in mn)
check("cron یادآوری", "sv_mod.run_reminders()" in mn)
check("متن ao_", 'state_name.startswith("ao_")' in mn)

for r in ["ao_m_", "ao_rot_", "ao_send_", "ao_rc_", "ao_dw_",
          "aom_", "aoj_", "aol_", "arc_",
          "sv_rep_", "sv_txt_", "sv_send_", "sv_rem_", "sv_xl_",
          "fbeva_", "fbevs_"]:
    check(f"مسیر {r}", r in mn)

ev = Path("events.py").read_text(encoding="utf-8")
check("ساخت خودکار در ذخیرهٔ رویداد", "_aa.sync_on_enable" in ev)
check("پیام جلسات خودکار", "جلسهٔ حضور و غیاب خودکار" in ev)
check("دکمهٔ گزارش نظرسنجی", 'sv_rep_{eid}' in ev)
check("ستون survey_audience", "survey_audience" in ev)
check("ستون session_repeat", "session_repeat" in ev)

att = Path("attendance.py").read_text(encoding="utf-8")
check("ساخت خودکار در صفحهٔ حضور", "_aa.sync_on_enable" in att)
check("دکمهٔ آنلاین", '"🌐 آنلاین"' in att)
check("ستون dwell_minutes", "dwell_minutes" in att)

ffs = Path("form_fill.py").read_text(encoding="utf-8")
check("قلاب نظرسنجی", "_sv.on_form_submit" in ffs)


# ══════════════════════════════════════════════════════════
section("۶) واژه‌نامه")
# ══════════════════════════════════════════════════════════
import re
for fn in ["survey.py", "attendance_auto.py"]:
    bad = []
    inq = False
    for i, ln in enumerate(Path(fn).read_text(encoding="utf-8")
                           .splitlines(), 1):
        if "«" in ln and "»" not in ln:
            inq = True
        elif "»" in ln and "«" not in ln:
            inq = False
            continue
        if inq or ln.lstrip().startswith("#"):
            continue
        if "«" in ln and "»" in ln:
            continue
        if re.search(r"گواهی(?!نامه)(?! می)(?!\w)", ln):
            bad.append(str(i))
    check(f"«گواهینامه» در {fn}", not bad, " · ".join(bad[:3]))


print(f"\n{'=' * 62}")
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if ERRORS:
    print("\n❌ خطاها:")
    for e in ERRORS[:30]:
        print(f"   • {e}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۳۳ پاس شدند!")
