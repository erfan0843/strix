"""
تست جریان واقعی پیام‌ها — بدون mock کردن send_or_edit

این تست دقیقاً بررسی می‌کند که هر کلیک چه اتفاقی می‌افتد:
  • آیا پیام ویرایش شد یا جدید ساخته شد؟
  • آیا روی پیام درست ویرایش شد؟
  • آیا وقتی بله امکانی را نداشته باشد، ربات کار می‌کند؟
"""
# This is an executable integration harness, not a pytest module. Keep it
# runnable directly while preventing pytest collection from sending requests
# or mutating its temporary database as an import side effect.
if __name__ != "__main__":
    import pytest
    pytest.skip("Run this mocked-flow harness directly with Python.", allow_module_level=True)

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="noraflow_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1", "BROADCAST_RATE": "999",
})

import bale_api  # noqa: E402

CALLS = []
MID = [1000]
FAIL_METHODS = set()   # متدهایی که بله پشتیبانی نمی‌کند


def _api(m, p=None, **k):
    p = p or {}
    if m in FAIL_METHODS:
        CALLS.append({"m": m, "ok": False, "p": p})
        return {"ok": False, "description": "Bad Request: method not found"}
    if m == "sendMessage":
        import json as J
        if "copy_text" in J.dumps(p.get("reply_markup") or {}) \
                and "copy_text" in FAIL_METHODS:
            CALLS.append({"m": "sendMessage", "ok": False, "p": p})
            return {"ok": False, "description": "BUTTON_TYPE_INVALID"}
        MID[0] += 1
        CALLS.append({"m": "sendMessage", "ok": True, "mid": MID[0],
                      "text": (p.get("text") or "")[:50], "p": p})
        return {"ok": True, "result": {"message_id": MID[0]}}
    if m == "editMessageText":
        import json as J
        if "copy_text" in J.dumps(p.get("reply_markup") or {}) \
                and "copy_text" in FAIL_METHODS:
            CALLS.append({"m": "editMessageText", "ok": False, "p": p})
            return {"ok": False, "description": "Bad Request: BUTTON_TYPE_INVALID"}
        CALLS.append({"m": "editMessageText", "ok": True,
                      "mid": p.get("message_id"),
                      "text": (p.get("text") or "")[:50], "p": p})
        return {"ok": True, "result": {"message_id": p.get("message_id")}}
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    if m == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if m == "getChat":
        return {"ok": True, "result": {"title": "x"}}
    CALLS.append({"m": m, "ok": True, "p": p})
    return {"ok": True, "result": {"message_id": MID[0]}}


bale_api.api = _api
bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.answer_callback = lambda *a, **k: {"ok": True}

import database, auth, profile as pf, admin as ad  # noqa: E402
import import_excel as ie, events as ev, attendance as att  # noqa: E402
import settings_admin as sa, main as M  # noqa: E402

sa.get_bot_username = lambda: "nora_bot"

database.init_db()
ev.init_event_tables()
att.init_attendance_tables()
database.seed_default_settings()
sa.seed_phase5_settings()
auth.ensure_super_admin(100000001)

S = 100000001
U = 555000

PASS, FAIL = [], []


def check(n, c, d=""):
    if c:
        PASS.append(n); print(f"  ✅ {n}")
    else:
        FAIL.append((n, d)); print(f"  ❌ {n}  {d}")


def sends():
    return [c for c in CALLS if c["m"] == "sendMessage" and c.get("ok")]


def edits():
    return [c for c in CALLS if c["m"] == "editMessageText"]


def cb(uid, data, mid):
    """کلیک روی دکمه یک پیام مشخص"""
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": data,
            "message": {"chat": {"id": uid}, "message_id": mid}}


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


print("\n" + "=" * 62)
print("🧪 تست جریان واقعی پیام‌ها")
print("=" * 62)


print("\n[۱] منوی ناوبری — باید ویرایش شود، نه پیام جدید")
CALLS.clear()
M.process_message(msg(S, "/start"))
first = sends()[-1]["mid"]
check("منوی اصلی ارسال شد", bool(first))

CALLS.clear()
M.handle_callback(cb(S, "admin_panel", first))
e = edits()
check("🐛 پنل ادمین همان پیام را ویرایش کرد", len(e) == 1, f"{len(e)} ویرایش")
check("🐛 روی message_id درست", e and e[0]["mid"] == first,
      f"{e[0]['mid'] if e else '-'} != {first}")
check("پیام جدید نساخت", len(sends()) == 0, f"{len(sends())} پیام جدید")

CALLS.clear()
M.handle_callback(cb(S, "admin_users", first))
check("لیست کاربران هم ویرایش شد", len(edits()) == 1)
check("همان پیام", edits()[0]["mid"] == first if edits() else False)

CALLS.clear()
M.handle_callback(cb(S, "admin_settings", first))
M.handle_callback(cb(S, "set_texts", first))
M.handle_callback(cb(S, "admin_panel", first))
check("۳ کلیک پشت‌سرهم = ۳ ویرایش", len(edits()) == 3, f"{len(edits())}")
check("همه روی یک پیام", all(x["mid"] == first for x in edits()))
check("هیچ پیام جدیدی ساخته نشد", len(sends()) == 0, f"{len(sends())}")


print("\n[۲] کلیک روی پیام قدیمی — باید همان قدیمی ویرایش شود")
CALLS.clear()
M.handle_callback(cb(S, "admin_stats", 500))   # پیام قدیمی
check("🐛 روی پیام قدیمی ویرایش شد",
      edits() and edits()[0]["mid"] == 500,
      f"{edits()[0]['mid'] if edits() else '-'}")


print("\n[۳] ویزارد — باید پیام جدید بفرستد (چون کاربر تایپ می‌کند)")
CALLS.clear()
M.handle_callback(cb(S, "ev_new", first))
M.handle_callback(cb(S, "ev_go", first))
n1 = len(sends())
M.process_message(msg(S, "کارگاه تست"))
M.process_message(msg(S, "توضیحات"))
n2 = len(sends())
check("🐛 هر مرحله پیام جدید می‌فرستد", n2 > n1, f"{n1}→{n2}")

CALLS.clear()
M.handle_callback(cb(S, "evt_workshop", MID[0]))
check("انتخاب نوع → پیام جدید (نه ویرایش)",
      len(sends()) >= 1, f"send={len(sends())} edit={len(edits())}")


print("\n[۴] تاگل قابلیت‌ها — باید ویرایش شود")
M.handle_callback(cb(S, "evl_online", MID[0]))
M.process_message(msg(S, "https://ble.ir/x"))
M.process_message(msg(S, "1404/06/20"))
M.process_message(msg(S, "18:00"))
M.process_message(msg(S, "90"))
M.process_message(msg(S, "20"))
M.handle_callback(cb(S, "evpay_0", MID[0]))
M.handle_callback(cb(S, "evp_public", MID[0]))
feat_mid = MID[0]
CALLS.clear()
M.handle_callback(cb(S, "evf_has_survey", feat_mid))
check("🐛 تاگل قابلیت پیام را ویرایش کرد",
      len(edits()) == 1 and edits()[0]["mid"] == feat_mid,
      f"send={len(sends())} edit={len(edits())}")


print("\n[۵] ذخیره رویداد تا انتها")
M.handle_callback(cb(S, "evf_done", feat_mid))
M.process_message(msg(S, "10"))
M.process_message(msg(S, "خط زندگی"))
M.process_message(msg(S, "⏭️ رد کردن"))
CALLS.clear()
before = database.db_scalar("SELECT COUNT(*) FROM events")
M.handle_callback(cb(S, "ev_save_publish", MID[0]))
after = database.db_scalar("SELECT COUNT(*) FROM events")
check("🐛 رویداد واقعاً ذخیره شد", after == before + 1, f"{before}→{after}")
allt = " ".join((c.get("text") or "") for c in CALLS)
check("پیام تأیید نمایش داده شد", "ذخیره شد" in allt, allt[:80])
EID = database.db_scalar("SELECT MAX(id) FROM events")


print("\n[۶] پیام همگانی — جریان کامل")
for i in range(3):
    database.db_execute("""INSERT INTO users
        (bale_user_id, first_name, mobile, is_authenticated, profile_status,
         referral_code, is_vip, city, gender)
        VALUES (?,?,?,1,'approved',?,?,?,?)""",
        (U + i, f"کاربر{i}", f"091200000{i:02d}", f"R{U+i}",
         1 if i == 0 else 0, "تهران" if i < 2 else "قم",
         "مرد" if i % 2 == 0 else "زن"))

CALLS.clear()
M.handle_callback(cb(S, "admin_broadcast", first))
check("منوی فیلتر ویرایش شد", len(edits()) >= 1)
kb = (edits()[-1]["p"].get("reply_markup") or {}) if edits() else {}
labels = [b["text"] for r in kb.get("inline_keyboard", []) for b in r]
check("🐛 فیلترها موجودند", len(labels) >= 9, f"{len(labels)}")
check("تعداد روی دکمه", any("(" in x and ")" in x for x in labels))

CALLS.clear()
M.handle_callback(cb(S, "bcf_vip", first))
d = auth.get_state_data(S)
check("filter ذخیره شد", d.get("filter") == "vip", str(d)[:80])

M.process_message(msg(S, "پیام تست همگانی"))
d = auth.get_state_data(S)
check("🐛 ready=1", d.get("ready") == 1, str(d)[:100])
check("🐛 متن ذخیره شد", d.get("text") == "پیام تست همگانی")

CALLS.clear()
M.handle_callback(cb(S, "bc_go", MID[0]))
got = [c for c in sends() if c["p"].get("chat_id") == U]
check("🐛 به کاربر VIP رسید", len(got) >= 1, f"{len(got)}")
notgot = [c for c in sends() if c["p"].get("chat_id") == U + 1]
check("🐛 به غیرVIP نرسید", len(notgot) == 0, f"{len(notgot)}")
check("گزارش پایانی", any("تمام شد" in (c.get("text") or "") for c in sends()))


print("\n[۷] دعوت لینکی")
CALLS.clear()
M.handle_callback(cb(U, "u_referral", 700))
txt = " ".join(str(c["p"].get("text") or "") for c in CALLS if c.get("p"))
check("🐛 لینک قابل کلیک", "https://ble.ir/nora_bot?start=" in txt, txt[:150])
check("کد در لینک", f"R{U}" in txt or f"NORA{U}" in txt, txt[:150])


print("\n[۸] وقتی بله ویرایش پیام را پشتیبانی نکند")
FAIL_METHODS.add("editMessageText")
CALLS.clear()
M.handle_callback(cb(S, "admin_panel", first))
check("🐛 fallback به پیام جدید", len(sends()) >= 1,
      "هیچ پیامی ارسال نشد — کاربر چیزی نمی‌بیند!")
FAIL_METHODS.discard("editMessageText")


print("\n[۹] وقتی بله copy_text را پشتیبانی نکند")
FAIL_METHODS.add("copy_text")
bale_api._supports_copy_text["v"] = None
CALLS.clear()
M.handle_callback(cb(U, "u_referral", 701))
delivered = [c for c in CALLS
             if c["m"] in ("sendMessage", "editMessageText") and c.get("ok")]
check("🐛 با حذف دکمه کپی دوباره ارسال شد", len(delivered) >= 1,
      "کاربر هیچ پیامی نمی‌بیند!")
import json as _J
has_copy = any("copy_text" in _J.dumps(c["p"].get("reply_markup") or {})
               for c in delivered)
check("دکمه copy_text حذف شد", not has_copy)
FAIL_METHODS.discard("copy_text")
bale_api._supports_copy_text["v"] = None


print("\n[۱۰] وقتی بله ری‌اکشن را پشتیبانی نکند")
FAIL_METHODS.add("setMessageReaction")
CALLS.clear()
try:
    M.process_message(msg(U, "سلام"))
    check("🐛 ربات کرش نکرد", True)
    check("پیام کاربر پردازش شد", len(sends()) >= 1)
except Exception as e:
    check("🐛 ربات کرش نکرد", False, str(e))
FAIL_METHODS.discard("setMessageReaction")


print("\n[۱۱] حالت عیب‌یابی")
CALLS.clear()
M.process_message(msg(S, "/debug on"))
check("debug روشن شد", database.get_setting("debug_mode") == "1")
CALLS.clear()
M.handle_callback(cb(S, "callback_ناشناخته_xyz", first))
txt = " ".join((c.get("text") or "") for c in sends())
check("🐞 دکمه بدون هندلر گزارش شد", "بدون هندلر" in txt, txt[:80])
M.process_message(msg(S, "/debug off"))
check("debug خاموش شد", database.get_setting("debug_mode") == "0")


print("\n[۱۲] هیچ دکمه‌ای بدون پاسخ نماند")
# همه callback های موجود در کیبوردها را استخراج و تست کن
import re
src = "".join(Path(ROOT, f).read_text(encoding="utf-8")
              for f in ["bale_api.py", "events.py", "admin.py",
                        "settings_admin.py", "attendance.py", "profile.py"])
statics = set(re.findall(r'"callback_data":\s*"([^"{]+)"', src))
statics.discard("noop")
tested = 0
silent = []
for c in sorted(statics):
    CALLS.clear()
    try:
        M.handle_callback(cb(S, c, first))
        tested += 1
        if not sends() and not edits():
            silent.append(c)
    except Exception as e:
        silent.append(f"{c} (کرش: {e})")
check(f"🐛 همه {tested} دکمه پاسخ می‌دهند", not silent,
      f"بی‌پاسخ: {silent[:5]}")



print("\n[۱۳] 📈 پوشش ویرایش در جا (فاز ۷)")
import ast as _ast
import re as _re

REPLY_KB = {"kb_cancel", "kb_skip", "kb_remove", "kb_gender", "kb_education",
            "kb_otp", "kb_contact", "kb_location", "kb_persistent"}
_bad_kb, _in_loop = [], []
for _f in ["events.py", "admin.py", "settings_admin.py", "attendance.py",
           "profile.py", "import_excel.py", "main.py"]:
    _src = Path(ROOT, _f).read_text(encoding="utf-8")
    _t = _ast.parse(_src)
    for _n in _ast.walk(_t):
        if not isinstance(_n, _ast.Call):
            continue
        _fn = _n.func
        _nm = _fn.id if isinstance(_fn, _ast.Name) else getattr(_fn, "attr", None)
        if _nm != "send_or_edit":
            continue
        for _a in list(_n.args[2:3]) + [k.value for k in _n.keywords if k.arg == "kb"]:
            if isinstance(_a, _ast.Call):
                _an = (_a.func.id if isinstance(_a.func, _ast.Name)
                       else getattr(_a.func, "attr", ""))
                if _an in REPLY_KB:
                    _bad_kb.append(f"{_f}:{_n.lineno}→{_an}")
    # حلقه
    _lines = _src.split("\n")
    _stack = []
    for _i, _l in enumerate(_lines):
        _ind = len(_l) - len(_l.lstrip())
        _st = _l.strip()
        while _stack and _ind <= _stack[-1]:
            _stack.pop()
        if _st.startswith(("for ", "while ")):
            _stack.append(_ind)
        if "send_or_edit(" in _l and _stack:
            _in_loop.append(f"{_f}:{_i+1}")

check("🛡️ هیچ send_or_edit با کیبورد reply نیست", not _bad_kb, str(_bad_kb[:3]))
check("🛡️ هیچ send_or_edit داخل حلقه نیست", not _in_loop, str(_in_loop[:3]))

# پوشش کلی
_ts = _te = 0
for _f in ["events.py", "admin.py", "settings_admin.py", "attendance.py",
           "profile.py", "main.py", "import_excel.py"]:
    _s2 = Path(ROOT, _f).read_text(encoding="utf-8")
    _s2 = _re.sub(r"def send_or_edit[\s\S]*?(?=\ndef )", "", _s2)
    _te += len(_re.findall(r"\bsend_or_edit\(", _s2))
    _ts += len(_re.findall(r"(?<!_)(?<!\.)\bsend\(cid", _s2))
_pct = _te * 100 // (_ts + _te) if (_ts + _te) else 0
check(f"📈 پوشش ویرایش در جا ({_te}/{_ts+_te} = {_pct}%)", _pct >= 18,
      f"{_pct}% — باید حداقل ۱۸٪ باشد")

# منوهای کلیدی حتماً ویرایش شوند
_menu_fns = [
    ("admin.py", "show_admin_panel"), ("admin.py", "show_user_list"),
    ("admin.py", "show_user_detail"), ("admin.py", "show_stats"),
    ("admin.py", "show_force_join_settings"),
    ("events.py", "show_admin_events"), ("events.py", "show_event_admin"),
    ("events.py", "show_user_events"), ("events.py", "show_event_user"),
    ("events.py", "show_my_events"), ("events.py", "event_report"),
    ("attendance.py", "show_sessions"), ("attendance.py", "show_session"),
    ("attendance.py", "my_certificates"),
    ("attendance.py", "user_attendance_menu"),
    ("settings_admin.py", "show_settings"), ("settings_admin.py", "show_texts"),
    ("settings_admin.py", "show_referral"), ("settings_admin.py", "show_points"),
    ("settings_admin.py", "payment_test_menu"),
    ("profile.py", "show_profile"),
]
_miss = []
for _f, _fn in _menu_fns:
    _src = Path(ROOT, _f).read_text(encoding="utf-8")
    _t = _ast.parse(_src)
    for _n in _ast.walk(_t):
        if isinstance(_n, _ast.FunctionDef) and _n.name == _fn:
            _seg = _ast.get_source_segment(_src, _n) or ""
            if "send_or_edit(" not in _seg:
                _miss.append(f"{_f}:{_fn}")
check(f"🎯 {len(_menu_fns)} منوی کلیدی ویرایش در جا دارند",
      not _miss, f"بدون ویرایش: {_miss}")

print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 جریان پیام‌ها سالم است!")
sys.exit(0)
