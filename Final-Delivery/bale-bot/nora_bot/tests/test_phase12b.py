"""
تست فاز ۱۲-ب — باشگاه کاربران و تیکت پشتیبانی

  🎖️ دستاوردها  •  🛍️ فروشگاه پاداش  •  🏆 رتبه‌بندی  •  📱 تیکت
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora12b_")
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
    SENT.append({"m": "editMessageText", "p": {"cid": cid, "text": text, "kb": kb}})
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

import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import main as M  # noqa: E402

for mod in (F, PAY, EV, AT, OC, AL, CL, TK, M):
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


def cbdata():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        out = [b.get("callback_data") for r in kb.get("inline_keyboard", [])
               for b in r if isinstance(b, dict) and b.get("callback_data")]
        if out:
            return out
    return []


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001
U1, U2, U3 = 950101, 950102, 950103

print("=" * 62)
print("🧪 تست فاز ۱۲-ب — باشگاه و تیکت")
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

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, nm in ((U1, "علی"), (U2, "سارا"), (U3, "رضا")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"0914{u}", "phone")


# ═══════ ۱) دستاوردها ═══════
print("\n[۱] دستاوردها")
check("جدول achievements", bool(database.db_execute(
    "SELECT name FROM sqlite_master WHERE name='achievements'", fetch="one")))
check("۱۳ دستاورد پیش‌فرض",
      database.db_scalar("SELECT COUNT(*) FROM achievements") >= 13,
      str(database.db_scalar("SELECT COUNT(*) FROM achievements")))
check("۴ سطح", len(CL.TIERS) == 4)

_bad = [a["trigger"] for a in database.db_execute(
    "SELECT DISTINCT trigger FROM achievements", fetch="all") or []
    if a["trigger"] not in OC.TRIGGERS]
check("همه شرط‌ها معتبرند", not _bad, str(_bad))
_high = database.db_scalar("SELECT COUNT(*) FROM achievements WHERE points>100")
check("🔴 هیچ دستاوردی بیش از ۱۰۰ امتیاز نیست", _high == 0, str(_high))

# حضور در کارگاه
eid = database.db_execute("""INSERT INTO events (title,event_type,status)
    VALUES ('کارگاه','workshop','published')""")
database.db_execute("""INSERT INTO event_registrations
    (event_id,bale_user_id,status,attended) VALUES (?,?,'attended',1)""",
    (eid, U1))
SENT.clear()
n, pts = CL.check_achievements(U1, "event_attend")
check("نشان «اولین قدم» داده شد", n >= 1, str(n))
check("امتیاز داده شد", pts > 0, str(pts))
check("پیام نشان ارسال شد", "نشان جدید" in alltext())
check("سطح در پیام", "برنزی" in alltext() or "🥉" in alltext())
_n2, _ = CL.check_achievements(U1, "event_attend")
check("نشان تکراری داده نمی‌شود", _n2 == 0)
check("در جدول ثبت شد", database.db_scalar(
    "SELECT COUNT(*) FROM user_achievements WHERE bale_user_id=?", (U1,)) >= 1)

SENT.clear()
M.handle_callback(cb(U1, "cl_my"))
check("صفحه دستاوردهای من", "دستاوردهای من" in last())
check("نوار پیشرفت", "▓" in last() or "░" in last())
check("امتیاز نمایش", "امتیاز" in last())
SENT.clear()
M.handle_callback(cb(U1, "cl_all"))
check("همه دستاوردها", "همه دستاوردها" in last())
check("سطح‌بندی", "برنزی" in last() and "طلایی" in last())

# سقف امتیاز روی دستاورد
database.db_execute("UPDATE achievements SET points=999 WHERE key='profile_pro'")
database.db_execute("UPDATE users SET complete_profile_percent=100 "
                    "WHERE bale_user_id=?", (U2,))
_b = database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                        (U2,)) or 0
CL.check_achievements(U2, "profile_complete")
_a = database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                        (U2,)) or 0
check("🔴 سقف امتیاز روی دستاورد اعمال شد", _a - _b <= 50, f"{_b}->{_a}")


# ═══════ ۲) فروشگاه ═══════
print("\n[۲] فروشگاه پاداش")
check("۵ پاداش پیش‌فرض",
      database.db_scalar("SELECT COUNT(*) FROM rewards") >= 5)
check("۳ نوع پاداش", len(CL.REWARD_TYPES) == 3)

database.db_execute("UPDATE users SET total_points=100 WHERE bale_user_id=?",
                    (U1,))
SENT.clear()
M.handle_callback(cb(U1, "cl_shop"))
check("صفحه فروشگاه", "فروشگاه پاداش" in last())
check("امتیاز کاربر نمایش", "100" in last())
check("پاداش گران قفل است", "🔒" in last() or "نیاز به" in last())

_r10 = database.db_execute("SELECT * FROM rewards WHERE key='disc10'",
                           fetch="one")
SENT.clear()
M.handle_callback(cb(U1, f"cl_buy_{_r10['id']}"))
check("تأیید خرید", "تأیید خرید" in last())
check("باقیمانده نمایش", "باقیمانده" in last())

SENT.clear()
M.handle_callback(cb(U1, f"cl_buyok_{_r10['id']}"))
_after = database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                            (U1,))
check("امتیاز کسر شد", _after == 100 - int(_r10["cost"]), str(_after))
check("خرید ثبت شد", database.db_scalar(
    "SELECT COUNT(*) FROM reward_redemptions WHERE bale_user_id=?", (U1,)) == 1)
check("کد تخفیف ساخته شد", "کد تخفیف" in alltext())
_dc = database.db_execute("""SELECT * FROM event_discount_codes
    WHERE created_by=? ORDER BY id DESC LIMIT 1""", (U1,), fetch="one")
check("کد در جدول تخفیف", bool(_dc))
check("درصد درست", _dc and _dc["amount"] == 10, str(_dc and _dc["amount"]))
check("فروش شمرده شد", database.db_execute(
    "SELECT sold FROM rewards WHERE id=?", (_r10["id"],),
    fetch="one")["sold"] == 1)

# امتیاز ناکافی
SENT.clear()
M.handle_callback(cb(U3, f"cl_buy_{_r10['id']}"))
check("🔒 امتیاز ناکافی رد شد", "امتیاز کافی" in last())

# سقف هر کاربر
SENT.clear()
database.db_execute("UPDATE users SET total_points=500 WHERE bale_user_id=?",
                    (U1,))
M.handle_callback(cb(U1, f"cl_buyok_{_r10['id']}"))
check("سقف هر کاربر رعایت شد", "حداکثر" in alltext(), alltext()[-70:])

# موجودی
database.db_execute("UPDATE rewards SET stock=1, sold=1 WHERE key='vip30'")
_vip = database.db_execute("SELECT * FROM rewards WHERE key='vip30'",
                           fetch="one")
SENT.clear()
M.handle_callback(cb(U1, f"cl_buyok_{_vip['id']}"))
check("⛔ موجودی تمام‌شده رد شد", "موجودی" in alltext())
database.db_execute("UPDATE rewards SET stock=0, sold=0 WHERE key='vip30'")

# VIP خودکار
database.db_execute("UPDATE users SET total_points=500, is_vip=0 "
                    "WHERE bale_user_id=?", (U2,))
SENT.clear()
M.handle_callback(cb(U2, f"cl_buyok_{_vip['id']}"))
check("⭐ VIP خودکار فعال شد", database.db_execute(
    "SELECT is_vip FROM users WHERE bale_user_id=?", (U2,),
    fetch="one")["is_vip"] == 1)

# جایزه دستی → در انتظار ادمین
_book = database.db_execute("SELECT * FROM rewards WHERE key='book'",
                            fetch="one")
database.db_execute("UPDATE users SET total_points=500 WHERE bale_user_id=?",
                    (U3,))
SENT.clear()
M.handle_callback(cb(U3, f"cl_buyok_{_book['id']}"))
_rd = database.db_execute("""SELECT * FROM reward_redemptions
    WHERE bale_user_id=? ORDER BY id DESC LIMIT 1""", (U3,), fetch="one")
check("جایزه دستی در انتظار", _rd and _rd["status"] == "pending")
check("ادمین مطلع شد", any(s["p"].get("cid") == S for s in SENT))

SENT.clear()
M.handle_callback(cb(S, "cl_reqs"))
check("لیست درخواست‌ها", "درخواست‌های پاداش" in last())
_before = database.db_scalar("SELECT total_points FROM users "
                             "WHERE bale_user_id=?", (U3,))
M.handle_callback(cb(S, f"cl_rej_{_rd['id']}"))
_after3 = database.db_scalar("SELECT total_points FROM users "
                             "WHERE bale_user_id=?", (U3,))
check("رد درخواست → امتیاز برگشت",
      _after3 == _before + int(_rd["cost"]), f"{_before}->{_after3}")

SENT.clear()
M.handle_callback(cb(U1, "cl_myredeem"))
check("سابقه خرید", "خریدهای من" in last())


# ═══════ ۳) رتبه‌بندی ═══════
print("\n[۳] جدول رتبه‌بندی")
check("۴ نوع جدول", len(CL.BOARDS) == 4)
for b in CL.BOARDS:
    SENT.clear()
    M.handle_callback(cb(U1, f"cl_bd_{b}"))
    check(f"جدول {CL.BOARDS[b]['name']}", "رتبه‌بندی" in last())

SENT.clear()
M.handle_callback(cb(U1, "cl_bd_points"))
check("مدال طلا", "🥇" in last())
check("«شما» مشخص شده", "← شما" in last())

database.set_setting("board_anonymous", "1", "t", "club")
SENT.clear()
M.handle_callback(cb(U3, "cl_bd_points"))
check("🕶️ نام‌ها مخفی شد", "***" in last(), last()[:120])
database.set_setting("board_anonymous", "0", "t", "club")

database.set_setting("board_enabled", "0", "t", "club")
SENT.clear()
M.handle_callback(cb(U1, "cl_bd_points"))
check("جدول خاموش کار نمی‌کند", "غیرفعال" in last())
database.set_setting("board_enabled", "1", "t", "club")


# ═══════ ۴) تیکت ═══════
print("\n[۴] تیکت پشتیبانی")
check("۶ دسته", len(TK.CATEGORIES) == 6)
check("۴ وضعیت", len(TK.STATUSES) == 4)
check("۴ اولویت", len(TK.PRIORITIES) == 4)

SENT.clear()
M.handle_callback(cb(U1, "tk_my"))
check("تیکت‌های من", "تیکت پشتیبانی" in last())
SENT.clear()
M.handle_callback(cb(U1, "tk_new"))
check("انتخاب دسته", sum(1 for d in cbdata() if d.startswith("tk_cat_")) == 6)

M.handle_callback(cb(U1, "tk_cat_payment"))
check("state تیکت", auth.get_state_name(U1) == TK.STATE_TK_NEW)
M.process_message(msg(U1, "ا"))
check("موضوع کوتاه رد شد", "۳ حرف" in last())
M.process_message(msg(U1, "مشکل در پرداخت کارگاه"))
check("توضیحات خواسته شد", "توضیحات" in last())
SENT.clear()
M.process_message(msg(U1, "پول کم شد ولی ثبت‌نام انجام نشد"))
_t = database.db_execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 1",
                         fetch="one")
check("تیکت ساخته شد", bool(_t))
check("کد پیگیری", _t and _t["code"].startswith("TK"))
check("دسته درست", _t and _t["category"] == "payment")
check("وضعیت باز", _t and _t["status"] == "open")
check("پیام اول ثبت شد", database.db_scalar(
    "SELECT COUNT(*) FROM ticket_messages WHERE ticket_id=?", (_t["id"],)) == 1)
check("ادمین مطلع شد", any(s["p"].get("cid") == S and "تیکت جدید"
                           in str(s["p"].get("text") or "") for s in SENT))
check("state پاک شد", auth.get_state_name(U1) is None)

SENT.clear()
M.handle_callback(cb(U1, f"tk_v_{_t['id']}"))
check("مشاهده تیکت", "#" + _t["code"] in last())
check("گفتگو نمایش", "پول کم شد" in last())

SENT.clear()
M.handle_callback(cb(S, f"tk_r_{_t['id']}"))
M.process_message(msg(S, "بررسی شد، مبلغ تا ۴۸ ساعت برمی‌گردد"))
_t2 = TK.get_ticket(_t["id"])
check("وضعیت پاسخ‌داده‌شده", _t2["status"] == "answered")
check("کاربر مطلع شد", any(s["p"].get("cid") == U1 for s in SENT))
check("unread کاربر", _t2["unread_user"] == 1)
SENT.clear()
M.handle_callback(cb(U1, f"tk_v_{_t['id']}"))
check("بعد مشاهده unread صفر", TK.get_ticket(_t["id"])["unread_user"] == 0)

M.handle_callback(cb(S, f"tk_prs_urgent_{_t['id']}"))
check("اولویت فوری", TK.get_ticket(_t["id"])["priority"] == "urgent")
M.handle_callback(cb(S, f"tk_s_closed_{_t['id']}"))
check("تیکت بسته شد", TK.get_ticket(_t["id"])["status"] == "closed")
SENT.clear()
M.handle_callback(cb(U1, f"tk_r_{_t['id']}"))
check("تیکت بسته پاسخ نمی‌گیرد", "بسته است" in last())

M.handle_callback(cb(U1, f"tk_rt_5_{_t['id']}"))
check("⭐ امتیاز ثبت شد", TK.get_ticket(_t["id"])["rating"] == 5)

# سقف تیکت باز
for i in range(3):
    database.db_execute("""INSERT INTO tickets (code,bale_user_id,subject,status)
        VALUES (?,?,?,'open')""", (f"TKX{i}", U2, f"t{i}"))
SENT.clear()
M.handle_callback(cb(U2, "tk_new"))
check("سقف تیکت باز رعایت شد", "تیکت باز دارید" in last())

SENT.clear()
M.handle_callback(cb(S, "tk_admin"))
check("پنل تیکت ادمین", "تیکت‌ها" in last())
SENT.clear()
M.handle_callback(cb(S, "tk_stats"))
check("آمار پشتیبانی", "آمار پشتیبانی" in last())
check("رضایت نمایش", "رضایت" in last())

# دسترسی
SENT.clear()
M.handle_callback(cb(U3, f"tk_v_{_t['id']}"))
check("🔒 تیکت دیگران دیده نمی‌شود", "دسترسی ندارید" in last())
PM.set_role(U3, "event_admin", S)
SENT.clear()
M.handle_callback(cb(U3, "tk_admin"))
check("🔒 ادمین بدون tk_manage رد شد", "دسترسی کافی" in last())
PM.set_role(U3, "broadcast_admin", S)
SENT.clear()
M.handle_callback(cb(U3, "tk_admin"))
check("✅ ادمین اطلاع‌رسانی تیکت می‌بیند", "تیکت" in last())
PM.revoke_admin(U3)


# ═══════ ۵) پنل و دسترسی باشگاه ═══════
print("\n[۵] پنل باشگاه")
SENT.clear()
M.handle_callback(cb(S, "cl_panel"))
check("پنل باشگاه", "باشگاه کاربران" in last())
SENT.clear()
M.handle_callback(cb(S, "cl_adm_ach"))
check("مدیریت دستاوردها", "مدیریت دستاوردها" in last())
SENT.clear()
M.handle_callback(cb(S, "cl_adm_rw"))
check("مدیریت فروشگاه", "مدیریت فروشگاه" in last())

_a1 = database.db_execute("SELECT id FROM achievements WHERE key='first_step'",
                          fetch="one")["id"]
M.handle_callback(cb(S, f"cln_points_{_a1}"))
M.process_message(msg(S, "999"))
check("🔴 سقف روی ورودی ادمین", database.db_execute(
    "SELECT points FROM achievements WHERE id=?", (_a1,),
    fetch="one")["points"] <= 100)

M.handle_callback(cb(S, "cl_aadd"))
M.process_message(msg(S, "قهرمان | event_attend | 50 | 60"))
check("دستاورد سفارشی", bool(database.db_execute(
    "SELECT id FROM achievements WHERE title='قهرمان'", fetch="one")))
M.handle_callback(cb(S, "cl_aadd"))
M.process_message(msg(S, "بد | شرط_غلط | 1 | 10"))
check("شرط نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(S, "🔙 بازگشت"))

M.handle_callback(cb(S, "cl_radd"))
M.process_message(msg(S, "تخفیف ۳۰٪ | 150 | discount | 30"))
check("پاداش سفارشی", bool(database.db_execute(
    "SELECT id FROM rewards WHERE title='تخفیف ۳۰٪'", fetch="one")))

SENT.clear()
M.handle_callback(cb(S, "cl_settings"))
check("تنظیمات باشگاه", "تنظیمات باشگاه" in last())
M.handle_callback(cb(S, "cl_tog_shop_enabled"))
check("فروشگاه خاموش شد", database.get_setting("shop_enabled") == "0")
SENT.clear()
M.handle_callback(cb(U1, "cl_shop"))
check("فروشگاه خاموش پیام می‌دهد", "بسته است" in last())
M.handle_callback(cb(S, "cl_tog_shop_enabled"))

SENT.clear()
M.handle_callback(cb(U1, "cl_panel"))
check("🔒 کاربر عادی پنل نمی‌بیند", "دسترسی ندارید" in last())


# ═══════ ۶) ورودی خراب ═══════
print("\n[۶] مقاومت")
bad = ["cl_buy_", "cl_buy_abc", "cl_buy_99999", "cl_buyok_x",
       "cl_av_99999", "cl_rv_abc", "cl_atg_x", "cl_rdel_99999",
       "cln_evil_1", "clrn_bad_1", "cl_tog_evil", "cl_bd_bad",
       "cl_ok_99999", "cl_rej_abc",
       "tk_v_", "tk_v_abc", "tk_v_99999", "tk_r_x", "tk_s_bad_1",
       "tk_prs_zz_1", "tk_rt_9_1", "tk_cat_bad", "tk_p_x_open",
       "tk_rate_99999"]
crashed = []
for d in bad:
    try:
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", not crashed, str(crashed[:2]))


# ═══════ ۷) یکپارچگی ═══════
print("\n[۷] یکپارچگی")
check("نشان تکراری نیست", database.db_scalar(
    """SELECT COUNT(*) FROM (SELECT bale_user_id,achievement_key
       FROM user_achievements GROUP BY bale_user_id,achievement_key
       HAVING COUNT(*)>1)""") == 0)
check("امتیاز منفی نیست",
      database.db_scalar("SELECT COUNT(*) FROM users WHERE total_points<0") == 0)
check("هزینه منفی نیست",
      database.db_scalar("SELECT COUNT(*) FROM rewards WHERE cost<0") == 0)
check("کد تیکت یکتاست", database.db_scalar(
    """SELECT COUNT(*) FROM (SELECT code FROM tickets
       GROUP BY code HAVING COUNT(*)>1)""") == 0)
check("پیام تیکت یتیم نیست", database.db_scalar(
    """SELECT COUNT(*) FROM ticket_messages m WHERE NOT EXISTS
       (SELECT 1 FROM tickets t WHERE t.id=m.ticket_id)""") == 0)
check("خرید یتیم نیست", database.db_scalar(
    """SELECT COUNT(*) FROM reward_redemptions r WHERE NOT EXISTS
       (SELECT 1 FROM rewards w WHERE w.key=r.reward_key)""") == 0)
check("وضعیت تیکت معتبر", database.db_scalar(
    f"""SELECT COUNT(*) FROM tickets WHERE status NOT IN
        ({','.join('?' * len(TK.STATUSES))})""", tuple(TK.STATUSES)) == 0)

print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\n❌ تست‌های ناموفق:")
    for f_ in FAILED:
        print(f"   • {f_}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۲-ب پاس شدند!")
