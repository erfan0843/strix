"""
تست فاز ۱۴ — قرعه‌کشی + داشبورد ۹ گزارش تخصصی

از فایل معماری:
  خط ۵۷۷۸۱ → ۶ روش انتخاب برنده، ۳ زمان اجرا، جوایز چندگانه
  خط ۴۲۳۱۰ → داشبورد + ۹ گزارش + دوره زمانی + هشدار خودکار
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora14_")
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
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption,
                                    "kb": kb, "path": str(f)}})
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
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import finance as FIN  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import lottery as LT  # noqa: E402
import reports as RP  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402
from types import SimpleNamespace  # noqa: E402

for mod in (F, PAY, EV, AT, OC, AL, FIN, CL, TK, LT, RP, AD, M):
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


_slug = [0]


def mkform(owner, ftype, title):
    """ساخت مستقیم فرم در دیتابیس"""
    _slug[0] += 1
    return database.db_execute(
        "INSERT INTO forms (owner_id, form_type, title, slug, status) "
        "VALUES (?,?,?,?,'active')",
        (owner, ftype, title, f"f{_slug[0]}"))


S = 100000001
A_EV, A_RP = 930001, 930002
U = [940001, 940002, 940003, 940004, 940005]

# گزارش این آزمون از پاسخ تجمیعی سرور mock می‌شود؛ هیچ query گزارش به SQLite نمی‌رود.
def _shared_report_identity(uid):
    role = "owner" if uid == S else "manager" if uid in (A_EV, A_RP) else None
    permissions = {"rp_view", "rp_export"} if role else set()
    if role == "owner":
        permissions.add("finance")
    return SimpleNamespace(role=role, has_permission=lambda key: key in permissions)


def _shared_report_summary(uid, period):
    return {
        "source": "shared_server_database", "period": period,
        "generated_at": "2026-10-01T00:00:00+00:00",
        "forms": {"total": 3, "created_in_period": 1, "by_status": {"published": 2, "draft": 1}},
        "responses": {"total": 8, "by_status": {"accepted": 6, "waitlisted": 2}},
        "accounts": {"total": 12, "by_role": {"manager": 2, "club-supervisor": 1}},
        "reviews": {"total": 2, "by_kind": {
            "profile_review": {"pending": 1}, "receipt_review": {"approved": 1},
        }},
        "notifications": {"total": 5, "by_delivery_status": {"delivered": 4, "pending": 1}},
        "cooperation_requests": {"total": 2, "by_status": {"new": 2}},
        "coverage": {"financial_amounts": "not_included"},
    }


M.shared_reports_mod.shared_api = SimpleNamespace(
    get_identity=_shared_report_identity,
    get_report_summary=_shared_report_summary,
    SharedAPIError=__import__("shared_api").SharedAPIError,
)
M.shared_reports_mod._SELECTED_PERIOD.clear()

print("=" * 62)
print("🧪 تست فاز ۱۴ — قرعه‌کشی + داشبورد گزارشات")
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
auth.create_auth_user({"id": A_RP, "first_name": "کاوه"}, "09132222222", "phone")
PM.set_role(A_EV, "event_admin", S)
PM.set_role(A_RP, "report_admin", S)

names = ["علی", "زهرا", "محمد", "سارا", "حسین"]
for i, u in enumerate(U):
    auth.create_auth_user({"id": u, "first_name": names[i]},
                          f"0913{5000000 + u}", "phone")


# ═══════════ ۱) ساختار پایه ═══════════
print("\n[۱] 🎲 ساختار قرعه‌کشی")

check("۶ روش انتخاب برنده", len(LT.WINNER_MODES) == 6,
      str(list(LT.WINNER_MODES)))
for m in ("disabled", "random", "highest_score", "fastest", "combined",
          "manual"):
    check(f"روش {m}", m in LT.WINNER_MODES)
check("۳ زمان اجرا", len(LT.DRAW_TIMES) == 3, str(list(LT.DRAW_TIMES)))

tabs = {r["name"] for r in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")}
for t in ("form_lotteries", "lottery_prizes", "lottery_winners"):
    check(f"جدول {t}", t in tabs)

check("متن‌های قرعه‌کشی seed شد",
      database.get_setting("lt_txt_winner", "") != "")


# ═══════════ ۲) ساخت قرعه‌کشی برای فرم ═══════════
print("\n[۲] 📝 قرعه‌کشی فرم مسابقه")

fid = mkform(S, "contest", "مسابقه فن‌بیان")
check("فرم مسابقه ساخته شد", bool(fid))

SENT.clear()
M.handle_callback(cb(S, f"lt_form_{fid}"))
check("پنل قرعه‌کشی باز شد", "قرعه‌کشی" in last(), last()[:50])

lot = LT.find_lottery("form", fid)
check("قرعه‌کشی در دیتابیس ساخته شد", bool(lot))
check("۳ جایزه پیش‌فرض", len(LT.get_prizes(lot["id"])) == 3,
      str(len(LT.get_prizes(lot["id"]))))
check("روش پیش‌فرض تصادفی", lot["winner_mode"] == "random")
check("وضعیت pending", lot["status"] == "pending")

lid = lot["id"]

# دوباره زدن نباید قرعه‌کشی دوم بسازد
M.handle_callback(cb(S, f"lt_form_{fid}"))
n = database.db_scalar("SELECT COUNT(*) FROM form_lotteries WHERE form_id=?",
                       (fid,))
check("قرعه‌کشی تکراری ساخته نشد", n == 1, str(n))


# ═══════════ ۳) تنظیم روش و زمان ═══════════
print("\n[۳] 🎯 روش انتخاب و زمان")

SENT.clear()
M.handle_callback(cb(S, f"lt_mode_{lid}"))
check("صفحه روش‌ها", "روش انتخاب برنده" in last())
check("۶ دکمه روش",
      sum(1 for d in allcb() if d.startswith("lt_setm_")) == 6)

M.handle_callback(cb(S, f"lt_setm_highest_score_{lid}"))
check("روش عوض شد",
      LT.get_lottery(lid)["winner_mode"] == "highest_score")

SENT.clear()
M.handle_callback(cb(S, f"lt_setm_evil_{lid}"))
check("🔒 روش نامعتبر رد شد", "نامعتبر" in last())

SENT.clear()
M.handle_callback(cb(S, f"lt_when_{lid}"))
check("صفحه زمان اجرا", "زمان اجرا" in last())
M.handle_callback(cb(S, f"lt_setw_scheduled_{lid}"))
check("زمان scheduled شد",
      LT.get_lottery(lid)["draw_time"] == "scheduled")

SENT.clear()
M.handle_callback(cb(S, f"lt_date_{lid}"))
check("درخواست تاریخ", "تاریخ" in last())
M.process_message(msg(S, "abc"))
check("🔒 تاریخ نامعتبر رد شد", "قالب" in last(), last()[:40])
M.process_message(msg(S, "1404/06/20"))
check("تاریخ ذخیره شد", LT.get_lottery(lid)["draw_at"] == "1404/06/20",
      str(LT.get_lottery(lid)["draw_at"]))

M.handle_callback(cb(S, f"lt_setw_manual_{lid}"))
check("برگشت به دستی", LT.get_lottery(lid)["draw_time"] == "manual")


# ═══════════ ۴) جوایز ═══════════
print("\n[۴] 🎁 مدیریت جوایز")

SENT.clear()
M.handle_callback(cb(S, f"lt_prz_{lid}"))
check("صفحه جوایز", "جوایز" in last())
check("۳ جایزه نمایش داده شد",
      sum(1 for d in allcb() if d.startswith("lt_pv_")) == 3)

SENT.clear()
M.handle_callback(cb(S, f"lt_padd_{lid}"))
check("افزودن جایزه شروع شد", "افزودن جایزه" in last())
M.process_message(msg(S, "کارت هدیه, 2, 50"))
prizes = LT.get_prizes(lid)
check("جایزه چهارم اضافه شد", len(prizes) == 4, str(len(prizes)))
p4 = prizes[-1]
check("عنوان درست", p4["title"] == "کارت هدیه", str(p4["title"]))
check("تعداد برنده ۲", p4["winner_count"] == 2, str(p4["winner_count"]))
check("امتیاز ۵۰", p4["points_reward"] == 50, str(p4["points_reward"]))
check("مجموع برندگان ۵", LT.total_winner_slots(lid) == 5,
      str(LT.total_winner_slots(lid)))

SENT.clear()
M.handle_callback(cb(S, f"lt_pv_{p4['id']}"))
check("جزئیات جایزه", "کارت هدیه" in last())

M.handle_callback(cb(S, f"ltn_count_{p4['id']}"))
M.process_message(msg(S, "3"))
check("تعداد برنده ویرایش شد",
      database.db_execute("SELECT winner_count FROM lottery_prizes WHERE id=?",
                          (p4["id"],), fetch="one")["winner_count"] == 3)

SENT.clear()
M.handle_callback(cb(S, f"ltn_count_{p4['id']}"))
M.process_message(msg(S, "999"))
check("🔒 سقف ۱۰۰ اعمال شد",
      database.db_execute("SELECT winner_count FROM lottery_prizes WHERE id=?",
                          (p4["id"],), fetch="one")["winner_count"] == 100)
M.handle_callback(cb(S, f"ltn_count_{p4['id']}"))
M.process_message(msg(S, "2"))

SENT.clear()
M.handle_callback(cb(S, f"lt_pdel_{p4['id']}"))
check("جایزه حذف شد", len(LT.get_prizes(lid)) == 3)

# جایزه بدون عنوان
SENT.clear()
M.handle_callback(cb(S, f"lt_padd_{lid}"))
M.process_message(msg(S, "   "))
check("🔒 عنوان خالی رد شد", "بنویسید" in last() or "خالی" in last(),
      last()[:40])
M.process_message(msg(S, "🔙 بازگشت"))
check("لغو کار کرد", len(LT.get_prizes(lid)) == 3)


# ═══════════ ۵) شرکت‌کنندگان و رتبه‌بندی ═══════════
print("\n[۵] 👥 شرکت‌کنندگان")

# ۵ پاسخ با نمره و زمان متفاوت
scores = [50, 90, 70, 90, 30]
for i, u in enumerate(U):
    database.db_execute("""INSERT INTO form_responses
        (form_id, bale_user_id, status, score, max_score,
         started_at, completed_at)
        VALUES (?,?,'completed',?,100,
                datetime('now', ?), datetime('now'))""",
        (fid, u, scores[i], f"-{10 - i} minutes"))

lot = LT.get_lottery(lid)
parts = LT.get_participants(lot)
check("۵ شرکت‌کننده", len(parts) == 5, str(len(parts)))
check("نمره خوانده شد", sorted(p["score"] for p in parts) == sorted(scores),
      str([p["score"] for p in parts]))
check("زمان محاسبه شد", all(p["time_taken"] > 0 for p in parts),
      str([p["time_taken"] for p in parts]))

# بالاترین نمره
ranked = LT.rank_participants(parts, "highest_score")
check("مرتب‌سازی نمره", ranked[0]["score"] == 90, str(ranked[0]["score"]))
check("آخری کمترین نمره", ranked[-1]["score"] == 30)

# سریع‌ترین
ranked_f = LT.rank_participants(parts, "fastest")
check("مرتب‌سازی سرعت",
      ranked_f[0]["time_taken"] <= ranked_f[-1]["time_taken"],
      f"{ranked_f[0]['time_taken']} <= {ranked_f[-1]['time_taken']}")

# ترکیبی: نمره اول، تساوی → زمان
ranked_c = LT.rank_participants(parts, "combined")
check("ترکیبی نمره اول", ranked_c[0]["score"] == 90)
top2 = [p for p in ranked_c[:2]]
check("در تساوی نمره، سریع‌تر جلوتر",
      top2[0]["time_taken"] <= top2[1]["time_taken"],
      f"{top2[0]['time_taken']} vs {top2[1]['time_taken']}")

# تصادفی — همه حاضرند
ranked_r = LT.rank_participants(parts, "random")
check("تصادفی همه را نگه می‌دارد", len(ranked_r) == 5)
check("تصادفی کسی را تکرار نمی‌کند",
      len({p["uid"] for p in ranked_r}) == 5)

# حداقل نمره
database.db_execute("UPDATE form_lotteries SET min_score=60 WHERE id=?",
                    (lid,))
p2 = LT.get_participants(LT.get_lottery(lid))
check("فیلتر حداقل نمره", len(p2) == 3, str(len(p2)))
check("همه بالای ۶۰", all(p["score"] >= 60 for p in p2))
database.db_execute("UPDATE form_lotteries SET min_score=0 WHERE id=?", (lid,))


# ═══════════ ۶) اجرای قرعه‌کشی ═══════════
print("\n[۶] 🎲 اجرای قرعه‌کشی")

SENT.clear()
M.handle_callback(cb(S, f"lt_draw_{lid}"))
check("صفحه تأیید", "تأیید نهایی" in last(), last()[:50])
check("دکمه اجرا هست", f"lt_go_{lid}" in allcb())
check("تعداد شرکت‌کننده نمایش داده شد", "5" in last())

SENT.clear()
M.handle_callback(cb(S, f"lt_go_{lid}"))
check("قرعه‌کشی انجام شد", "انجام شد" in alltext(), alltext()[:60])

lot = LT.get_lottery(lid)
check("وضعیت done", lot["status"] == "done", str(lot["status"]))
check("زمان اجرا ثبت شد", bool(lot["drawn_at"]))
check("تعداد شرکت‌کننده ذخیره شد", lot["participants_count"] == 5,
      str(lot["participants_count"]))

winners = LT.get_winners(lid)
check("۳ برنده انتخاب شد", len(winners) == 3, str(len(winners)))
check("رتبه‌ها ۱ تا ۳",
      sorted(w["rank_no"] for w in winners) == [1, 2, 3],
      str([w["rank_no"] for w in winners]))
check("همه کد پیگیری دارند", all(w["code"] for w in winners))
check("کدها یکتا هستند", len({w["code"] for w in winners}) == 3)
check("برنده تکراری نیست",
      len({w["bale_user_id"] for w in winners}) == 3)

# روش highest_score بود → برنده اول باید نمره ۹۰ باشد
check("برنده اول بالاترین نمره", winners[0]["score"] == 90,
      str(winners[0]["score"]))

# اطلاع‌رسانی
check("به برندگان پیام رفت", all(w["notified"] for w in winners),
      str([w["notified"] for w in winners]))
win_ids = {w["bale_user_id"] for w in winners}
for w in winners:
    check(f"پیام برنده {w['bale_user_id']}",
          any("برنده شدید" in t for t in to(w["bale_user_id"])))
losers = [u for u in U if u not in win_ids]
for lu in losers:
    check(f"پیام به بازنده {lu}",
          any("قرعه‌کشی" in t for t in to(lu)),
          str(to(lu))[:60])

# اجرای دوباره جلوگیری شود
SENT.clear()
M.handle_callback(cb(S, f"lt_go_{lid}"))
check("🔒 اجرای دوباره رد شد", "قبلاً" in last(), last()[:40])
check("تعداد برنده تغییر نکرد", len(LT.get_winners(lid)) == 3)


# ═══════════ ۷) نمایش و خروجی برندگان ═══════════
print("\n[۷] 🏆 برندگان")

SENT.clear()
M.handle_callback(cb(S, f"lt_win_{lid}"))
check("صفحه برندگان", "برندگان" in last())
check("نام برنده نمایش داده شد",
      any(n in last() for n in names), last()[:80])
check("کد پیگیری نمایش داده شد", "LT" in last())

SENT.clear()
M.handle_callback(cb(S, f"lt_exp_{lid}"))
check("خروجی Excel ساخته شد",
      any(s["m"] == "sendDocument" for s in SENT), last()[:50])

# نمای کاربر
winner_uid = winners[0]["bale_user_id"]
SENT.clear()
M.handle_callback(cb(winner_uid, f"ltu_form_{fid}"))
check("کاربر برنده نتیجه را می‌بیند", "برنده شدید" in last(), last()[:60])

loser_uid = losers[0]
SENT.clear()
M.handle_callback(cb(loser_uid, f"ltu_form_{fid}"))
check("کاربر بازنده نتیجه را می‌بیند", "برندگان" in last())
check("به بازنده «برنده شدید» نشان نمی‌دهد",
      "برنده شدید" not in last())


# ═══════════ ۸) بازنشانی و اجرای مجدد ═══════════
print("\n[۸] 🔄 اجرای مجدد")

SENT.clear()
M.handle_callback(cb(S, f"lt_reset_{lid}"))
check("تأیید بازنشانی", "مطمئن" in last(), last()[:40])
check("هنوز پاک نشده", len(LT.get_winners(lid)) == 3)

M.handle_callback(cb(S, f"lt_rsty_{lid}"))
check("برندگان پاک شدند", len(LT.get_winners(lid)) == 0)
check("وضعیت pending شد", LT.get_lottery(lid)["status"] == "pending")

# اجرای مجدد با روش تصادفی
M.handle_callback(cb(S, f"lt_setm_random_{lid}"))
SENT.clear()
M.handle_callback(cb(S, f"lt_go_{lid}"))
check("اجرای مجدد کار کرد", len(LT.get_winners(lid)) == 3)


# ═══════════ ۹) قرعه‌کشی رویداد ═══════════
print("\n[۹] 🎉 قرعه‌کشی رویداد")

eid = database.db_execute(
    "INSERT INTO events (title, event_type, status, capacity, created_by) "
    "VALUES ('همایش بهاره','conference','published',100,?)", (S,))
for u in U[:4]:
    database.db_execute("""INSERT INTO event_registrations
        (event_id, user_id, bale_user_id, status, attended)
        VALUES (?,?,?,'confirmed',?)""",
        (eid, auth.get_user(u)["id"], u, 1 if u in U[:2] else 0))

SENT.clear()
M.handle_callback(cb(S, f"lt_event_{eid}"))
check("قرعه‌کشی رویداد باز شد", "قرعه‌کشی" in last())
lot_e = LT.find_lottery("event", eid)
check("قرعه‌کشی رویداد ساخته شد", bool(lot_e))
check("source=event", lot_e["source"] == "event")

parts_e = LT.get_participants(lot_e)
check("۴ شرکت‌کننده رویداد", len(parts_e) == 4, str(len(parts_e)))

# فقط حاضرین
database.db_execute("UPDATE form_lotteries SET only_attended=1 WHERE id=?",
                    (lot_e["id"],))
parts_a = LT.get_participants(LT.get_lottery(lot_e["id"]))
check("فیلتر فقط حاضرین", len(parts_a) == 2, str(len(parts_a)))
database.db_execute("UPDATE form_lotteries SET only_attended=0 WHERE id=?",
                    (lot_e["id"],))

SENT.clear()
M.handle_callback(cb(S, f"lt_go_{lot_e['id']}"))
check("قرعه‌کشی رویداد اجرا شد",
      len(LT.get_winners(lot_e["id"])) == 3,
      str(len(LT.get_winners(lot_e["id"]))))

# دکمه در قابلیت‌های پیشرفته رویداد
SENT.clear()
EV.show_advanced(S, S, eid)
check("🎲 دکمه قرعه‌کشی در رویداد",
      f"lt_event_{eid}" in allcb(), str(allcb())[:100])

# دکمه در تنظیمات پیشرفته فرم
SENT.clear()
F.show_advanced(S, S, fid)
# 🔄 فاز ۴۰: صفحهٔ «⋮ پیشرفته» ۱۹ ردیف داشت و از سقف ۱۰
#    ردیف رد می‌شد. قرعه‌کشی · وبهوک · گردش کار · ارتباط ·
#    تأیید ادمین به لایهٔ دوم «⋮ بیشتر» منتقل شدند.
F.show_advanced2(S, S, fid)
check("🎲 دکمه قرعه‌کشی در فرم", f"lt_form_{fid}" in allcb())


# ═══════════ ۱۰) امتیاز جایزه ═══════════
print("\n[۱۰] 🏅 امتیاز جایزه")

fid2 = mkform(S, "contest", "مسابقه امتیازی")
lot2 = LT.ensure_lottery("form", fid2, S, "مسابقه امتیازی")
lid2 = lot2["id"]
database.db_execute("DELETE FROM lottery_prizes WHERE lottery_id=?", (lid2,))
database.db_execute("""INSERT INTO lottery_prizes
    (lottery_id, rank_order, icon, title, winner_count, points_reward)
    VALUES (?,1,'🥇','جایزه امتیازی',1,25)""", (lid2,))

pu = U[0]
database.db_execute("UPDATE users SET total_points=0 WHERE bale_user_id=?",
                    (pu,))
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, score, max_score)
    VALUES (?,?,'completed',80,100)""", (fid2, pu))

SENT.clear()
LT.run_draw(S, S, lid2)
pts = database.db_scalar("SELECT total_points FROM users "
                         "WHERE bale_user_id=?", (pu,))
check("امتیاز جایزه داده شد", pts > 0, str(pts))
check("امتیاز از سقف روزانه رد نشد", pts <= 50, str(pts))


# ═══════════ ۱۱) اجرای خودکار زمان‌بندی‌شده ═══════════
print("\n[۱۱] ⏰ اجرای خودکار")

fid3 = mkform(S, "contest", "مسابقه زمان‌دار")
lot3 = LT.ensure_lottery("form", fid3, S, "مسابقه زمان‌دار")
database.db_execute("""UPDATE form_lotteries SET draw_time='scheduled',
    draw_at='1400/01/01' WHERE id=?""", (lot3["id"],))
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, score) VALUES (?,?,'completed',10)""",
    (fid3, U[1]))

SENT.clear()
n_done, _ = LT.check_scheduled()
check("قرعه‌کشی گذشته اجرا شد", n_done >= 1, str(n_done))
check("وضعیت done شد",
      LT.get_lottery(lot3["id"])["status"] == "done")

# تاریخ آینده نباید اجرا شود
fid4 = mkform(S, "contest", "مسابقه آینده")
lot4 = LT.ensure_lottery("form", fid4, S, "مسابقه آینده")
database.db_execute("""UPDATE form_lotteries SET draw_time='scheduled',
    draw_at='1499/12/29' WHERE id=?""", (lot4["id"],))
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, score) VALUES (?,?,'completed',10)""",
    (fid4, U[2]))
LT.check_scheduled()
check("🔒 تاریخ آینده اجرا نشد",
      LT.get_lottery(lot4["id"])["status"] == "pending")


# ═══════════ ۱۲) لیست کلی قرعه‌کشی‌ها ═══════════
print("\n[۱۲] 📋 لیست قرعه‌کشی‌ها")

SENT.clear()
M.handle_callback(cb(S, "lt_all"))
check("لیست باز شد", "قرعه‌کشی" in last())
check("آمار نمایش داده شد", "کل" in last())
check("دکمه هر قرعه‌کشی",
      any(d.startswith("lt_v_") for d in allcb()))


# ═══════════ ۱۳) گزارش تجمیعی پایگاه مشترک ═══════════
print("\n[۱۳] 📊 گزارش تجمیعی پایگاه مشترک")

SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
d = allcb()
check("داشبورد سروری باز شد", "داشبورد گزارشات" in last(), last()[:70])
check("شمار حساب‌های مشترک", "حساب‌های بله" in last())
check("پوشش رویدادها روشن است", "رویدادها" in last())
check("فعالیت زنده جعل نمی‌شود", "لحظه‌ای" in last())
check("دوره نمایش داده شد", "دوره" in last())
for b in ("rp_events", "rp_users", "rp_forms", "rp_att", "rp_certs",
          "rp_notify", "rp_top", "rp_period", "lt_all"):
    check(f"دکمه {b}", b in d, str(d))
check("💰 مالی فقط برای مالک نمایش داده می‌شود", "rp_finance" in d)
check("👨‍💼 گزارش ادمین فقط برای مالک نمایش داده می‌شود", "rp_admins" in d)


# ═══════════ ۱۴) نماهای گزارش مشترک ═══════════
print("\n[۱۴] 📑 نماهای گزارش مشترک")
reports = [
    ("rp_events", "گزارش رویدادها"),
    ("rp_users", "گزارش کاربران"),
    ("rp_forms", "گزارش فرم‌ها"),
    ("rp_att", "گزارش حضور"),
    ("rp_finance", "گزارش مالی"),
    ("rp_certs", "گزارش گواهینامه‌ها"),
    ("rp_notify", "گزارش اطلاع‌رسانی"),
    ("rp_admins", "گزارش ادمین‌ها"),
    ("rp_top", "برترین‌ها"),
]
for data, expect in reports:
    SENT.clear()
    M.handle_callback(cb(S, data))
    check(expect, expect in last(), last()[:80])
check("گزارش‌ها فقط aggregate دارند", "amount" not in alltext() and "payload" not in alltext())
check("دادهٔ وصل‌نشده با عدد محلی جایگزین نمی‌شود",
      "هنوز در پایگاه مشترک ثبت نمی‌شود" in alltext())


# ═══════════ ۱۵) بازهٔ گزارش سروری ═══════════
print("\n[۱۵] 📅 بازهٔ گزارش سروری")

check("هفت بازهٔ آماده", len(M.shared_reports_mod._PERIODS) == 7)
SENT.clear()
M.handle_callback(cb(S, "rp_period"))
check("صفحه دوره‌ها", "دوره زمانی" in last())
check("همه دوره‌ها دکمه دارند",
      sum(1 for d in allcb() if d.startswith("rp_p_")) == 7)

M.handle_callback(cb(S, "rp_p_today"))
check("دوره امروز در حافظهٔ گزارش نشست",
      M.shared_reports_mod._SELECTED_PERIOD.get(str(S)) == "today")
SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
check("داشبورد بازهٔ امروز را می‌خواند", "امروز" in last())

M.handle_callback(cb(S, "rp_p_custom"))
check("🔒 دورهٔ نامعتبر رد شد",
      M.shared_reports_mod._SELECTED_PERIOD.get(str(S)) == "today")

M.handle_callback(cb(S, "rp_p_30d"))
check("بازگشت به ۳۰ روز",
      M.shared_reports_mod._SELECTED_PERIOD.get(str(S)) == "30d")

crashed = []
for period in M.shared_reports_mod._PERIODS:
    try:
        M.shared_reports_mod.pick_period(S, S, period)
        for data, _ in reports:
            SENT.clear()
            M.handle_callback(cb(S, data))
    except Exception as exc:
        crashed.append(f"{period}: {type(exc).__name__} {exc}")
check("همه بازه‌ها و نماها بدون کرش", not crashed, str(crashed[:2]))
M.shared_reports_mod._SELECTED_PERIOD[str(S)] = "30d"


# ═══════════ ۱۶) درصد تغییر و نوار ═══════════
print("\n[۱۶] 📈 محاسبات")

check("رشد مثبت", "▲" in RP.pct(150, 100), RP.pct(150, 100))
check("کاهش", "▼" in RP.pct(50, 100), RP.pct(50, 100))
check("بدون تغییر", "بدون تغییر" in RP.pct(100, 100))
check("جدید", "جدید" in RP.pct(10, 0))
check("صفر به صفر", RP.pct(0, 0) == "—", RP.pct(0, 0))

check("نوار کامل", RP.bar(10, 10) == "█" * 10, RP.bar(10, 10))
check("نوار خالی", RP.bar(0, 10) == "░" * 10)
check("نوار نصف", RP.bar(5, 10).count("█") == 5, RP.bar(5, 10))
check("تقسیم بر صفر امن", RP.bar(5, 0) == "░" * 10)


# ═══════════ ۱۷) هشدارها ═══════════
print("\n[۱۷] 💡 هشدارهای خودکار")

database.db_execute("""INSERT INTO profile_submissions
    (user_id, bale_user_id, status, profile_data)
    VALUES (?,?,'pending','{}')""", (auth.get_user(U[0])["id"], U[0]))
database.db_execute("""INSERT INTO tickets
    (code, bale_user_id, category, subject, status, unread_admin)
    VALUES ('TK1',?,'other','تست','open',1)""", (U[0],))

alerts = RP._build_alerts(S)
check("هشدار تولید شد", len(alerts) > 0, str(alerts))
check("هشدار پروفایل", any("پروفایل" in a for a in alerts), str(alerts))
check("هشدار تیکت", any("تیکت" in a for a in alerts), str(alerts))

SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
check("هشدار محلی وارد گزارش سروری نمی‌شود",
      "نیاز به توجه" not in last() and "پایگاه مشترک" in last(), last()[-200:])

tips = RP._build_tips(S, "30d")
check("توصیه‌ها بدون کرش", isinstance(tips, list))


# ═══════════ ۱۸) دسترسی گزارش‌ها ═══════════
print("\n[۱۸] 🔒 دسترسی")

SENT.clear()
M.handle_callback(cb(A_RP, "admin_stats"))
check("✅ گزارش‌گیر داشبورد می‌بیند", "داشبورد" in last(), last()[:50])
d_rp = allcb()
check("🔒 گزارش‌گیر مالی نمی‌بیند", "rp_finance" not in d_rp, str(d_rp))

SENT.clear()
M.handle_callback(cb(A_RP, "rp_finance"))
check("🔒 گارد گزارش مالی", "سوپرادمین" in last() or "دسترسی" in last(),
      last()[:50])

SENT.clear()
M.handle_callback(cb(A_EV, "rp_admins"))
check("🔒 ادمین رویداد گزارش ادمین نمی‌بیند", "دسترسی" in last())

SENT.clear()
M.handle_callback(cb(U[0], "admin_stats"))
check("🔒 کاربر عادی داشبورد ندارد", "دسترسی" in last())

SENT.clear()
M.handle_callback(cb(U[0], f"lt_v_{lid}"))
check("🔒 کاربر عادی پنل قرعه‌کشی ندارد", "دسترسی" in last())

SENT.clear()
M.handle_callback(cb(U[0], f"lt_go_{lid}"))
check("🔒 کاربر عادی قرعه‌کشی اجرا نمی‌کند",
      "دسترسی" in last() or "قبلاً" in last(), last()[:40])
check("برندگان دست‌نخورده", len(LT.get_winners(lid)) == 3)


# ═══════════ ۱۹) خروجی مشترک ═══════════
print("\n[۱۹] 📥 خروجی مشترک")

SENT.clear()
M.handle_callback(cb(S, "rp_export"))
docs = [s for s in SENT if s["m"] == "sendDocument"]
check("تا آماده‌شدن خروجی مشترک فایل محلی ساخته نمی‌شود",
      not docs and "پایگاه مشترک" in last(), last()[:80])
SENT.clear()
M.handle_callback(cb(A_RP, "rp_export"))
docs2 = [s for s in SENT if s["m"] == "sendDocument"]
check("خروجی مدیر هم به فایل محلی fallback نمی‌کند",
      not docs2 and "پایگاه مشترک" in last(), last()[:80])


# ═══════════ ۲۰) ورودی‌های خراب ═══════════
print("\n[۲۰] 🛡️ ورودی‌های خراب")

bad = [
    "lt_v_", "lt_v_abc", "lt_v_999999", "lt_form_abc", "lt_event_999999",
    "lt_mode_x", "lt_setm_", "lt_setm_evil_1", "lt_setm_random_999999",
    "lt_when_x", "lt_setw_evil_1", "lt_date_abc",
    "lt_prz_x", "lt_padd_999999", "lt_pv_abc", "lt_pdel_999999",
    "ltn_", "ltn_evil_1", "ltn_count_abc", "ltn_minscore_abc",
    "lt_cond_x", "lt_notif_x", "lt_tog_evil_1", "lt_tog_is_admin_1",
    "lt_draw_abc", "lt_go_999999", "lt_win_x", "lt_reset_abc",
    "lt_rsty_999999", "lt_exp_abc", "lt_pg_abc",
    "ltu_form_abc", "ltu_event_999999",
    "rp_p_", "rp_p_evil", "rp_events", "rp_export", "lt_all",
]
crashed = []
for dd in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(S, dd))
    except Exception as e:
        crashed.append(f"{dd}: {type(e).__name__} {e}")
check("ادمین: هیچ کرشی", not crashed, str(crashed[:3]))

crashed2 = []
for dd in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(U[0], dd))
    except Exception as e:
        crashed2.append(f"{dd}: {type(e).__name__} {e}")
check("کاربر عادی: هیچ کرشی", not crashed2, str(crashed2[:3]))

# state های خراب
for st in (LT.STATE_LT_ADD, LT.STATE_LT_NUM, LT.STATE_LT_DATE):
    try:
        auth.set_state(S, st, {"lid": lid, "pid": 999999,
                               "field": "count"}, merge=False)
        SENT.clear()
        M.process_message(msg(S, "!@#$"))
    except Exception as e:
        check(f"state {st}", False, str(e))
auth.clear_state(S)
check("state های قرعه‌کشی سالم", True)

# قرعه‌کشی بدون شرکت‌کننده
fid5 = mkform(S, "contest", "مسابقه خالی")
lot5 = LT.ensure_lottery("form", fid5, S, "خالی")
SENT.clear()
M.handle_callback(cb(S, f"lt_draw_{lot5['id']}"))
check("🔒 بدون شرکت‌کننده اجرا نمی‌شود",
      "شرکت‌کننده" in last(), last()[:50])

# قرعه‌کشی بدون جایزه
database.db_execute("DELETE FROM lottery_prizes WHERE lottery_id=?",
                    (lot5["id"],))
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, score) VALUES (?,?,'completed',5)""",
    (fid5, U[3]))
SENT.clear()
M.handle_callback(cb(S, f"lt_draw_{lot5['id']}"))
check("🔒 بدون جایزه اجرا نمی‌شود", "جایزه" in last(), last()[:50])

# روش disabled
database.db_execute("""INSERT INTO lottery_prizes
    (lottery_id, rank_order, icon, title, winner_count)
    VALUES (?,1,'🥇','تست',1)""", (lot5["id"],))
M.handle_callback(cb(S, f"lt_setm_disabled_{lot5['id']}"))
SENT.clear()
M.handle_callback(cb(S, f"lt_go_{lot5['id']}"))
check("🔒 روش غیرفعال اجرا نمی‌شود", "غیرفعال" in last(), last()[:50])


# ═══════════ ۲۱) لاگ فارسی ═══════════
print("\n[۲۱] 📋 لاگ فارسی")

import re as _re
_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))
for k in ("lottery_created", "lottery_draw", "lottery_prize",
          "lottery_reset", "report_export"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۲۲) یکپارچگی ═══════════
print("\n[۲۲] 🧩 یکپارچگی")

check("هیچ برنده بدون قرعه‌کشی نیست",
      (database.db_scalar("""SELECT COUNT(*) FROM lottery_winners w
          WHERE NOT EXISTS (SELECT 1 FROM form_lotteries l
                            WHERE l.id=w.lottery_id)""") or 0) == 0)
check("هیچ جایزه یتیم نیست",
      (database.db_scalar("""SELECT COUNT(*) FROM lottery_prizes p
          WHERE NOT EXISTS (SELECT 1 FROM form_lotteries l
                            WHERE l.id=p.lottery_id)""") or 0) == 0)
check("رتبه‌ها مثبت‌اند",
      (database.db_scalar("SELECT COUNT(*) FROM lottery_winners "
                          "WHERE rank_no < 1") or 0) == 0)
check("امتیاز منفی نشد",
      (database.db_scalar("SELECT COUNT(*) FROM users "
                          "WHERE total_points < 0") or 0) == 0)

# برنده تکراری در یک قرعه‌کشی
dup = database.db_scalar("""SELECT COUNT(*) FROM (
    SELECT lottery_id, bale_user_id, COUNT(*) c FROM lottery_winners
    GROUP BY lottery_id, bale_user_id HAVING c > 1)""") or 0
check("هیچ برنده تکراری در یک قرعه‌کشی نیست", dup == 0, str(dup))

check("همه قرعه‌کشی‌های done برنده دارند",
      all(len(LT.get_winners(r["id"])) > 0 for r in
          (database.db_execute("SELECT id FROM form_lotteries "
                               "WHERE status='done'", fetch="all") or [])))


# ═══════════ ۲۳) رگرسیون ═══════════
print("\n[۲۳] ♻️ رگرسیون")

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
p = allcb()
check("پنل ادمین سالم", "admin_users" in p and "admin_settings" in p)
check("پنل هنوز خلوت است", len(p) <= 8, str(len(p)))

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
check("پرداخت و مالی سالم", "پرداخت" in last())

SENT.clear()
M.handle_callback(cb(S, "fin_dash"))
check("داشبورد مالی سالم", "داشبورد مالی" in last())

SENT.clear()
M.handle_callback(cb(S, "um_admins"))
check("مدیریت ادمین‌ها سالم", "ادمین" in last())
check("لاگ زیر ادمین‌ها", "lg_list" in allcb())

SENT.clear()
M.process_message(msg(S, "/start"))
check("منوی مدیریتی سالم", "نورا" in alltext() or "سلام" in alltext())

SENT.clear()
M.process_message(msg(U[0], "/start"))
check("منوی کاربر سالم", "نورا" in alltext() or "سلام" in alltext())

SENT.clear()
M.process_message(msg(S, "📊 گزارش‌ها"))
check("دکمه گزارش‌ها → داشبورد جدید",
      "داشبورد گزارشات" in last(), last()[:50])

SENT.clear()
M.handle_callback(cb(S, "admin_stats_old"))
check("آمار قدیمی هنوز کار می‌کند", "آمار" in last())


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۴ پاس شدند!")
