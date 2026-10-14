"""
تست فاز ۲۶ — 🎫 بلیط تصویری فرم

درخواست کاربر (عیناً):
  «بریم سراغ بلیط. این بلیط دیجی‌فرمه، یه چیز ساده مثل بساز با
   ویژگی‌های این بلیط، فقط برای فرم فعال باشه: اسم رویداد، اسم شخص
   تکمیل‌کننده، کیوآرکد و شماره ثبت زیرش. اینو تو پنل مرتبط با بلیط
   قابل کم و زیاد و اضافه کردن باشه... لوگو ربات رو من میفرستم بعدا
   تو قسمت مدیریت بلیط، یه گوشه بلیط لوگو ربات باشه در هر بلیط.
   قالب بلیط هم یه چیز ساده... کلا بک‌گراندش رو بتونم اضافه کنم با
   تنظیم سایز بلیط»
"""
import io
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora26_")
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
    SENT.append({"m": "sendMessage", "p": {"cid": cid, "text": text,
                                           "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _photo(cid, p, cap=None, kb=None):
    FILES.append(str(p))
    SENT.append({"m": "sendPhoto", "p": {"cid": cid, "text": cap or "",
                                         "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api.send_photo = _photo
bale_api.send_document = lambda c, d, cap=None, kb=None: _photo(
    c, d, cap, kb)
bale_api._send_file = lambda m, k, c, f, cap=None, kb=None: _photo(
    c, f, cap, kb)
bale_api.answer_callback = lambda *a, **k: {"ok": True}
bale_api.get_file_info = lambda fid: {
    "ok": True, "result": {"file_path": f"srv/{fid}.png"}}

_FAKE_IMG = {}


def _dl(path):
    return _FAKE_IMG.get("blob")


bale_api.download_file = _dl

import config  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FF  # noqa: E402
import ticket as TK  # noqa: E402
import certgen as CG  # noqa: E402
import tickets as SUP  # noqa: E402
import permissions as PM  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, TK, CG, SUP, M):
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
    return "\n".join(texts())


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
            "message": {"message_id": 1,
                        "chat": {"id": uid, "type": "private"}}}


print("=" * 62)
print("🧪 تست فاز ۲۶ — بلیط تصویری فرم")
print("=" * 62)

database.init_db()
F.init_form_tables()
CG.init_cert_tables()
PM.init_permission_tables()
SUP.init_ticket_tables()
SUP.init_inbox_table()
database.seed_default_settings()

S = 100000001
U1, U2 = 2610001, 2610002
auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000",
                      "phone")
auth.ensure_super_admin(S)
auth.create_auth_user({"id": U1, "first_name": "عرفان",
                       "last_name": "خدابنده‌لو"}, "09121234567", "phone")
auth.create_auth_user({"id": U2, "first_name": "کاربر"}, "09121234568",
                      "phone")
database.db_execute("UPDATE users SET national_id=? WHERE bale_user_id=?",
                    ("0010247165", U1))

_pil = True
try:
    from PIL import Image
except ImportError:
    _pil = False


# ═══════════ ۱) 🧱 بلوک‌ها ═══════════
print("\n[۱] 🧱 بلوک‌های بلیط")

check("۱۵ بلوک تعریف شده", len(TK.BLOCKS) >= 15, str(len(TK.BLOCKS)))
_on = [b for b in TK.layout() if b["on"]]
check("پیش‌فرض ۵ بلوک روشن است", len(_on) == 5, str(len(_on)))
_keys = [b["key"] for b in _on]
for k in ("header", "name", "tracking", "qr", "serial"):
    check(f"بلوک «{k}» پیش‌فرض روشن", k in _keys)
check("ترتیب: کیوآر قبل از شماره ثبت",
      _keys.index("qr") < _keys.index("serial"))

check("همه بلوک‌ها متادیتا دارند",
      all(TK.block_meta(k) for k in TK.BLOCK_KEYS))


# ═══════════ ۲) 🖥️ پنل ═══════════
print("\n[۲] 🖥️ پنل مدیریت بلیط")

SENT.clear()
M.handle_callback(cb(S, "tk_panel"))
_t = last()
check("پنل باز شد", "بلیط فرم" in _t, _t[:50])
check("تعداد بلوک را می‌گوید", "بلوک فعال" in _t)
check("اندازه را می‌گوید", "اندازه" in _t)
check("وضعیت لوگو را می‌گوید", "لوگو" in _t)
for c in ("tk_blocks", "tk_style", "tk_size", "tk_assets",
          "tk_more", "tk_prev"):
    check(f"دکمه «{c}» هست", c in allcb())

SENT.clear()
M.handle_callback(cb(S, "tk_blocks"))
check("صفحه بلوک‌ها باز شد", "بلوک‌های بلیط" in last())
check("دکمه روشن/خاموش دارد",
      any(c.startswith("tkbt_") for c in allcb()))
check("دکمه جابه‌جایی دارد",
      any(c.startswith("tkdn_") for c in allcb()))
check("دکمه تنظیم بلوک دارد",
      any(c.startswith("tkbe_") for c in allcb()))


# ═══════════ ۳) ➕➖ کم و زیاد کردن ═══════════
print("\n[۳] ➕➖ کم و زیاد کردن بلوک")

_n0 = len([b for b in TK.layout() if b["on"]])
M.handle_callback(cb(S, "tkbt_date"))
_n1 = len([b for b in TK.layout() if b["on"]])
check("🔴 بلوک اضافه شد", _n1 == _n0 + 1, f"{_n0}→{_n1}")
M.handle_callback(cb(S, "tkbt_date"))
check("🔴 بلوک برداشته شد",
      len([b for b in TK.layout() if b["on"]]) == _n0)

_o0 = [b["key"] for b in TK.layout()]
M.handle_callback(cb(S, "tkdn_name"))
_o1 = [b["key"] for b in TK.layout()]
check("🔽 بلوک پایین رفت", _o0 != _o1, str(_o1[:3]))
M.handle_callback(cb(S, "tkup_name"))
check("🔼 بلوک بالا برگشت",
      [b["key"] for b in TK.layout()] == _o0)

_s0 = TK.block_of("name")["size"]
M.handle_callback(cb(S, "tksz_name_4"))
check("🔠 اندازه متن بزرگ شد",
      TK.block_of("name")["size"] == _s0 + 4)
M.handle_callback(cb(S, "tksz_name_-4"))
check("🔡 اندازه برگشت", TK.block_of("name")["size"] == _s0)
for _ in range(60):
    M.handle_callback(cb(S, "tksz_name_-2"))
check("🛡️ اندازه از حد پایین نمی‌رود",
      TK.block_of("name")["size"] >= 8,
      str(TK.block_of("name")["size"]))
TK.set_block_field("name", "size", 30)

SENT.clear()
M.handle_callback(cb(S, "tklb_tracking"))
check("صفحه برچسب باز شد", "برچسب" in last())
M.process_message(msg(S, "شماره ثبت‌نام:"))
check("🏷️ برچسب دلخواه ذخیره شد",
      TK.block_of("tracking")["label"] == "شماره ثبت‌نام:",
      str(TK.block_of("tracking")["label"]))
M.handle_callback(cb(S, "tklb_tracking"))
M.process_message(msg(S, "-"))
check("🏷️ با «-» برچسب حذف می‌شود",
      TK.block_of("tracking")["label"] == "")

M.handle_callback(cb(S, "tk_reset"))
check("♻️ بازگشت به پیش‌فرض",
      len([b for b in TK.layout() if b["on"]]) == 5)


# ═══════════ ۴) 🎨 ظاهر ═══════════
print("\n[۴] 🎨 رنگ و ظاهر")

SENT.clear()
M.handle_callback(cb(S, "tk_style"))
check("صفحه ظاهر باز شد", "ظاهر بلیط" in last())
check("۶ پالت آماده", len(TK.PALETTES) >= 6, str(len(TK.PALETTES)))
for p in ("cream", "mint", "sky", "night"):
    check(f"پالت «{p}» دکمه دارد", f"tkpal_{p}" in allcb())

M.handle_callback(cb(S, "tkpal_sky"))
check("🎨 پالت عوض شد", TK.s("tkf_palette") == "sky")
check("رنگ‌ها هم پر شدند", TK.s("tkf_bg") == "#E9F2FB",
      TK.s("tkf_bg"))
_bg, _bd, _bt, _tx = TK.palette()
check("رنگ به RGB تبدیل می‌شود", isinstance(_bg, tuple) and len(_bg) == 3)

M.handle_callback(cb(S, "tke_tkf_bg"))
M.process_message(msg(S, "2E8B67"))
check("🎨 رنگ دستی ذخیره شد (بدون #)",
      TK.s("tkf_bg") == "#2E8B67", TK.s("tkf_bg"))
check("رنگ دستی → پالت دلخواه",
      TK.s("tkf_palette") == "custom")
SENT.clear()
M.handle_callback(cb(S, "tke_tkf_bg"))
M.process_message(msg(S, "قرمز"))
check("🛡️ رنگ نامعتبر رد می‌شود", "درست نیست" in alltext())
M.handle_callback(cb(S, "tkpal_cream"))

_c0 = TK.s_on("tkf_corner")
M.handle_callback(cb(S, "tkb_tkf_corner"))
check("🔵 گوشهٔ تزئینی خاموش/روشن", TK.s_on("tkf_corner") != _c0)
M.handle_callback(cb(S, "tkb_tkf_corner"))
M.handle_callback(cb(S, "tkb_tkf_border"))
check("🖼️ کادر خاموش/روشن می‌شود", TK.s_on("tkf_border"))
M.handle_callback(cb(S, "tkb_tkf_border"))

M.handle_callback(cb(S, "tkal_center"))
check("📐 چیدمان عمودی عوض شد", TK.s("tkf_align") == "center")
M.handle_callback(cb(S, "tkal_spread"))


# ═══════════ ۵) 📐 اندازه ═══════════
print("\n[۵] 📐 اندازه بلیط")

SENT.clear()
M.handle_callback(cb(S, "tk_size"))
check("صفحه اندازه باز شد", "اندازه بلیط" in last())
check("۵ اندازه آماده", len(TK.SIZES) >= 5)

M.handle_callback(cb(S, "tksize_landscape"))
check("🖥️ افقی اعمال شد", TK.size_wh() == (1000, 600),
      str(TK.size_wh()))
M.handle_callback(cb(S, "tksize_story"))
check("📲 استوری اعمال شد", TK.size_wh() == (1080, 1920))

M.handle_callback(cb(S, "tksize_custom"))
M.handle_callback(cb(S, "tke_tkf_w"))
M.process_message(msg(S, "۷۲۰"))
check("✏️ پهنای دلخواه با عدد فارسی",
      TK.size_wh()[0] == 720, str(TK.size_wh()))
M.handle_callback(cb(S, "tke_tkf_h"))
M.process_message(msg(S, "9999"))
check("🛡️ اندازه از سقف بیشتر نمی‌شود",
      TK.size_wh()[1] <= 3000, str(TK.size_wh()))
M.handle_callback(cb(S, "tksize_portrait"))
check("📱 برگشت به عمودی", TK.size_wh() == (600, 800))


# ═══════════ ۶) 🖼️ رسم واقعی ═══════════
print("\n[۶] 🖼️ ساخت واقعی تصویر")

if _pil:
    _data = {
        "event": "کمپ تابستانی کارآفرینی",
        "form": "کمپ تابستانی کارآفرینی",
        "name": "عرفان خدابنده‌لو",
        "tracking": "TL6032POXZ8840",
        "serial": "cbea38a331",
        "qr_data": "cbea38a331",
        "date": "1404/05/12",
    }
    _p = TK.build(_data)
    check("🎫 تصویر ساخته شد", bool(_p) and Path(_p).exists(), str(_p))
    if _p:
        _im = Image.open(_p)
        check("📐 اندازه درست است", _im.size == (600, 800),
              str(_im.size))
        check("حجم منطقی", Path(_p).stat().st_size > 3000)

    # اندازه‌های مختلف
    for _sz, _wh in (("landscape", (1000, 600)),
                     ("square", (800, 800)),
                     ("card", (856, 540))):
        database.set_setting("tkf_size", _sz, "t", "ticket")
        database.clear_settings_cache()
        _p2 = TK.build(_data)
        _ok = _p2 and Image.open(_p2).size == _wh
        check(f"📐 اندازهٔ «{_sz}» درست رسم شد", _ok,
              str(Image.open(_p2).size) if _p2 else "—")
    database.set_setting("tkf_size", "portrait", "t", "ticket")
    database.clear_settings_cache()

    # همه بلوک‌ها روشن — نباید سرریز کند
    _it = TK.layout()
    for _b in _it:
        _b["on"] = 1
    TK.save_layout(_it)
    database.set_setting("tkf_note_text", "یادداشت تست", "t", "ticket")
    database.set_setting("tkf_footer_text", "پانویس تست", "t", "ticket")
    database.clear_settings_cache()
    _pall = TK.build(dict(_data, mobile="09121234567",
                          nid="0010247165", amount="500,000 ریال",
                          place="سالن اصلی"))
    check("🧱 با همهٔ بلوک‌ها هم می‌سازد",
          bool(_pall) and Path(_pall).exists())
    if _pall:
        check("📐 سرریز نکرده", Image.open(_pall).size == (600, 800))
    TK.reset_layout()

    # هیچ بلوکی روشن نباشد
    _it = TK.layout()
    for _b in _it:
        _b["on"] = 0
    TK.save_layout(_it)
    _pnone = TK.build(_data)
    check("🛡️ بدون هیچ بلوکی هم کرش نمی‌کند", bool(_pnone))
    TK.reset_layout()

    check("🛡️ داده خالی کرش نمی‌کند", bool(TK.build({})))
    check("🛡️ داده None کرش نمی‌کند", bool(TK.build(None)))
else:
    check("⚠️ Pillow نیست — رد شد", True)


# ═══════════ ۷) 🏛️ لوگو و پس‌زمینه ═══════════
print("\n[۷] 🏛️ لوگو و پس‌زمینه")

SENT.clear()
M.handle_callback(cb(S, "tk_assets"))
check("صفحه لوگو باز شد", "لوگو و پس‌زمینه" in last())
check("دکمه آپلود لوگو", "tka_logo" in allcb())
check("دکمه آپلود پس‌زمینه", "tka_bg" in allcb())
check("۶ جای لوگو تعریف شده", len(TK.LOGO_POS) == 6)

if _pil:
    _b = io.BytesIO()
    Image.new("RGBA", (200, 80), (30, 90, 200, 255)).save(_b, "PNG")
    _FAKE_IMG["blob"] = _b.getvalue()

    SENT.clear()
    M.handle_callback(cb(S, "tka_logo"))
    check("درخواست لوگو", "لوگو" in last())
    check("state درست", auth.get_state_name(S) == TK.STATE_TK_ASSET)
    M.process_update({"update_id": 1, "message": {
        "message_id": 5, "from": {"id": S},
        "chat": {"id": S, "type": "private"},
        "document": {"file_id": "L1", "file_name": "logo.png"}}})
    check("🏛️ لوگو ذخیره شد", bool(TK.asset_path("logo")),
          TK.asset_path("logo"))

    _p3 = TK.build(_data if _pil else {})
    check("🎫 بلیط با لوگو ساخته شد", bool(_p3))

    for _pos in ("tl", "bl", "br", "tc", "bc"):
        M.handle_callback(cb(S, f"tklp_{_pos}"))
        _pp = TK.build(_data)
        check(f"📍 لوگو در «{TK.LOGO_POS[_pos]}»", bool(_pp))
    M.handle_callback(cb(S, "tklp_tr"))

    M.handle_callback(cb(S, "tke_tkf_logo_size"))
    M.process_message(msg(S, "20"))
    check("📐 اندازهٔ لوگو عوض شد",
          TK.s_num("tkf_logo_size") == 20)

    # پس‌زمینه
    _b2 = io.BytesIO()
    Image.new("RGB", (900, 1200), (240, 220, 250)).save(_b2, "PNG")
    _FAKE_IMG["blob"] = _b2.getvalue()
    M.handle_callback(cb(S, "tka_bg"))
    M.process_update({"update_id": 2, "message": {
        "message_id": 6, "from": {"id": S},
        "chat": {"id": S, "type": "private"},
        "document": {"file_id": "B1", "file_name": "bg.png"}}})
    check("🌄 پس‌زمینه ذخیره شد", bool(TK.asset_path("bg")))

    for _mode in ("cover", "fit", "tile"):
        M.handle_callback(cb(S, f"tkbg_{_mode}"))
        _pb = TK.build(_data)
        check(f"🖼️ حالت «{_mode}» کار می‌کند", bool(_pb))
    M.handle_callback(cb(S, "tkbg_cover"))

    M.handle_callback(cb(S, "tkd_logo"))
    check("🗑️ لوگو حذف شد", not TK.asset_path("logo"))
    M.handle_callback(cb(S, "tkd_bg"))
    check("🗑️ پس‌زمینه حذف شد", not TK.asset_path("bg"))
else:
    check("⚠️ Pillow نیست — رد شد", True)


# ═══════════ ۸) 👁️ پیش‌نمایش ═══════════
print("\n[۸] 👁️ پیش‌نمایش زنده")

SENT.clear()
FILES.clear()
M.handle_callback(cb(S, "tk_prev"))
if _pil:
    check("🖼️ تصویر پیش‌نمایش فرستاده شد", len(FILES) > 0)
    check("پیام راهنما دارد", "پیش‌نمایش" in alltext()
          or "کاربر" in alltext())
    _n_before = TK.stats()["count"]
    M.handle_callback(cb(S, "tk_prev"))
    check("🧹 پیش‌نمایش فایل جا نمی‌گذارد",
          TK.stats()["count"] <= _n_before + 1)
else:
    check("⚠️ Pillow نیست — رد شد", True)


# ═══════════ ۹) 🎫 بلیط واقعی فرم ═══════════
print("\n[۹] 🎫 بلیط واقعی از پاسخ فرم")

FID = database.db_execute(
    "INSERT INTO forms (title,slug,form_type,status,owner_id,"
    "ticket_enabled) VALUES (?,?,?,?,?,?)",
    ("کمپ تابستانی کارآفرینی", "camp26", "registration", "active", S, 1))
RID = database.db_execute(
    "INSERT INTO form_responses (form_id,bale_user_id,status,"
    "tracking_code,qr_code,completed_at) VALUES (?,?,?,?,?,"
    "CURRENT_TIMESTAMP)",
    (FID, U1, "completed", "TL6032POXZ8840", "cbea38a331"))

if _pil:
    _pr = TK.build_for_response(RID)
    check("🎫 بلیط از پاسخ ساخته شد", bool(_pr) and Path(_pr).exists())
    check("نام فایل شامل کد پیگیری",
          _pr and "TL6032POXZ8840" in Path(_pr).name, str(_pr))

SENT.clear()
FILES.clear()
M.handle_callback(cb(U1, f"fftk_{RID}"))
if _pil:
    check("🔴 کاربر بلیط تصویری گرفت", len(FILES) > 0)
check("کپشن دارد", bool(alltext().strip()))

check("🛡️ پاسخ ناموجود کرش نمی‌کند",
      TK.build_for_response(99999) is None)

# خاموش کردن بلیط تصویری
M.handle_callback(cb(S, "tkb_tkf_on"))
check("🔴 بلیط تصویری خاموش شد", not TK.enabled())
SENT.clear()
FILES.clear()
M.handle_callback(cb(U1, f"fftk_{RID}"))
check("خاموش که شد، به موتور قدیمی برمی‌گردد",
      bool(alltext().strip()))
M.handle_callback(cb(S, "tkb_tkf_on"))
check("♻️ دوباره روشن شد", TK.enabled())


# ═══════════ ۱۰) ⚙️ تنظیمات بیشتر ═══════════
print("\n[۱۰] ⚙️ تنظیمات بیشتر")

SENT.clear()
M.handle_callback(cb(S, "tk_more"))
check("صفحه باز شد", "تنظیمات بیشتر" in last())
M.handle_callback(cb(S, "tke_tkf_custom1"))
M.process_message(msg(S, "با سپاس از همراهی شما"))
check("✏️ متن دلخواه ذخیره شد",
      TK.s("tkf_custom1") == "با سپاس از همراهی شما")
M.handle_callback(cb(S, "tke_tkf_keep_hours"))
M.process_message(msg(S, "24"))
check("⏰ مهلت نگهداری عوض شد", TK.s_num("tkf_keep_hours") == 24)

_n, _kb = TK.cleanup(force=True)
check("🧹 پاکسازی کار می‌کند", isinstance(_n, int))
check("آمار فایل درست است", TK.stats()["count"] == 0,
      str(TK.stats()))


# ═══════════ ۱۱) 🔗 مسیر در منو ═══════════
print("\n[۱۱] 🔗 دسترسی از هاب")

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("🎟️ بلیط فرم در هاب هست", "tk_panel" in allcb())
check("بلیط متنی رویداد هم هست", "ct_set_ticket" in allcb())

SENT.clear()
M.handle_callback(cb(S, "ct_set_ticket"))
check("♻️ بلیط متنی رویداد سالم", "بلیط" in last())
check("لینک به بلیط فرم دارد", "tk_panel" in allcb())


# ═══════════ ۱۲) 🔒 امنیت ═══════════
print("\n[۱۲] 🔒 دسترسی")

for d in ("tk_panel", "tk_blocks", "tk_style", "tk_size", "tk_assets",
          "tk_prev", "tkbt_name", "tka_logo", "tkpal_night"):
    SENT.clear()
    M.handle_callback(cb(U2, d))
    check(f"🔒 کاربر عادی: {d}",
          "دسترسی" in last() or "سوپرادمین" in last(), last()[:40])


# ═══════════ ۱۳) 🛡️ ورودی خراب ═══════════
print("\n[۱۳] 🛡️ ورودی‌های خراب")

for d in ("tkbt_nope", "tkbe_nope", "tkup_nope", "tkdn_nope",
          "tksz_x_y", "tksz_name_abc", "tklb_nope", "tkpal_bad",
          "tksize_bad", "tklp_bad", "tkbg_bad", "tkal_bad",
          "tka_bad", "tkd_bad", "tke_nope", "tkb_nope",
          "tkb_tkf_qr_size"):
    SENT.clear()
    try:
        M.handle_callback(cb(S, d))
        check(f"🛡️ «{d}» کرش نمی‌کند", True)
    except Exception as e:
        check(f"🛡️ «{d}» کرش نمی‌کند", False, str(e)[:70])

check("🛡️ block_of نامعتبر", TK.block_of("nope") is None)
check("🛡️ _hex نامعتبر", TK._hex("zzz") == (255, 255, 255))
check("🛡️ _hex کوتاه", TK._hex("#fff") == (255, 255, 255))
check("🛡️ asset_path ناموجود", TK.asset_path("nope") == "")


# ═══════════ ۱۴) 🛡️ رگرسیون ═══════════
print("\n[۱۴] 🛡️ رگرسیون")

# 🔴 مهم: ماژول تیکت پشتیبانی نباید قفل شده باشد
_main = (ROOT / "main.py").read_text(encoding="utf-8")
check("🔴 tickets و ticket تداخل نام ندارند",
      "import tickets as tk_mod" in _main
      and "import ticket as ftk_mod" in _main)
check("🔴 فراخوانی‌های بلیط فرم با ftk_mod است",
      "ftk_mod.show_panel" in _main)
check("🔴 تیکت پشتیبانی هنوز tk_mod دارد",
      "tk_mod.init_ticket_tables" in _main)

SENT.clear()
try:
    M.handle_callback(cb(U2, "u_tickets"))
    check("♻️ تیکت پشتیبانی کرش نمی‌کند", True)
except Exception as e:
    check("♻️ تیکت پشتیبانی کرش نمی‌کند", False, str(e)[:70])

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("♻️ هاب گواهینامه سالم", "گواهینامه" in last())

import guard as G  # noqa: E402
_f = G.check_new_features()
check("🛡️ همه قابلیت‌ها سالم", all(_f.values()),
      str([k for k, v in _f.items() if not v]))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۶ پاس شدند!")
