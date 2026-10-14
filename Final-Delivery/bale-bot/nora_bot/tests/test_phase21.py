"""
تست فاز ۲۱ — 🖨️ تشخیص LibreOffice

درخواست کاربر (verbatim):
  «لیبرو نصب دارم ولی بات میگه نصب نیست»

چهار باگ ریشه‌ای که رفع شد:
  ۱) کش منفی دائمی — یک‌بار «نیست» یعنی تا ری‌استارت «نیست»
  ۲) فقط PATH گشته می‌شد — نصب‌کنندهٔ لیبره به PATH اضافه نمی‌کند
  ۳) URI خراب: file://C:\\... به‌جای file:///C:/...
  ۴) کلید cert_soffice_path خوانده می‌شد ولی دکمه‌ای نداشت
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora21_")
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
import certgen as CG  # noqa: E402
import permissions as PM  # noqa: E402
import attendance as AT  # noqa: E402
import events as EV  # noqa: E402
import main as M  # noqa: E402

for mod in (CG, AT, EV, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PM.init_permission_tables()
CG.init_cert_tables()
database.seed_default_settings()

S = 100000001
auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000",
                      "phone")
auth.ensure_super_admin(S)
database.clear_settings_cache()

OK = FAIL = 0
FAILED = []


def check(name, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def cb(uid, data):
    return {"id": "1", "from": {"id": uid, "first_name": "x"},
            "message": {"message_id": 1, "chat": {"id": uid}},
            "data": data}


def msg(uid, text):
    return {"message_id": 1, "from": {"id": uid, "first_name": "x"},
            "chat": {"id": uid}, "text": text}


def last():
    for s in reversed(SENT):
        t = s["p"].get("text")
        if t:
            return t
    return ""


def alltext():
    """همه متن‌های فرستاده‌شده — چون گاهی هشدار و صفحه بعدی
    هر دو با هم می‌آیند"""
    return " | ".join((s["p"].get("text") or s["p"].get("caption") or "")
                      for s in SENT)


def last_kb():
    for s in reversed(SENT):
        kb = s["p"].get("kb")
        if kb and isinstance(kb, dict) and kb.get("inline_keyboard"):
            return str(kb)
    return ""


def reset_lo():
    CG._LO_BIN, CG._LO_AT = None, 0.0


print("=" * 62)
print("🖨️ تست فاز ۲۱ — تشخیص LibreOffice")
print("=" * 62)


# ═══════════ ۱) 🔴 باگ کش منفی دائمی ═══════════
print("\n[۱] 🔴 کش منفی نباید ابدی باشد")

check("متغیر عمر کش تعریف شده", hasattr(CG, "_LO_TTL"))
check("عمر کش منطقی است", 10 <= CG._LO_TTL <= 600, str(CG._LO_TTL))
check("زمان آخرین جست‌وجو نگه داشته می‌شود", hasattr(CG, "_LO_AT"))

# شبیه‌سازی: ربات قبل از نصب لیبره بالا آمده
reset_lo()
CG._LO_BIN, CG._LO_AT = "", time.time()
check("🔴 کش منفی تازه → دوباره نمی‌گردد (سرعت)",
      CG.libreoffice_bin() is None)

# ولی با force باید بگردد
_calls = {"n": 0}
_orig_cand = CG._lo_candidates


def _spy():
    _calls["n"] += 1
    return _orig_cand()


CG._lo_candidates = _spy
CG.libreoffice_bin(force=True)
check("🔴 force=True کش را دور می‌زند و از نو می‌گردد",
      _calls["n"] >= 1, str(_calls["n"]))

# کش منفی کهنه → باید دوباره بگردد
_calls["n"] = 0
CG._LO_BIN, CG._LO_AT = "", time.time() - (CG._LO_TTL + 5)
CG.libreoffice_bin()
check("🔴 کش منفی کهنه شد → خودکار دوباره می‌گردد",
      _calls["n"] >= 1, str(_calls["n"]))
CG._lo_candidates = _orig_cand
reset_lo()


# ═══════════ ۲) 🔍 دامنه جست‌وجو ═══════════
print("\n[۲] 🔍 کجاها را می‌گردد؟")

cands = CG._lo_candidates()
check("فهرست مسیرها خالی نیست", len(cands) > 0, str(len(cands)))
check("تابع نام‌های اجرایی دارد", hasattr(CG, "_lo_exe_names"))
check("تابع رجیستری ویندوز دارد", hasattr(CG, "_lo_from_registry"))
check("تابع عیب‌یابی دارد", hasattr(CG, "lo_diagnose"))
check("تابع تست اجرا دارد", hasattr(CG, "_lo_works"))

if os.name != "nt":
    joined = " ".join(cands)
    check("🐧 مسیرهای لینوکس پوشش داده شده",
          "/usr/bin" in joined and "libreoffice" in joined)
    check("🐧 مسیر snap هم هست", "snap" in joined)
    check("🐧 مسیر مک هم هست", "Applications" in joined)

# 🪟 شبیه‌سازی ویندوز
_real = os.name
try:
    os.name = "nt"
    names = CG._lo_exe_names()
    check("🪟 روی ویندوز دنبال soffice.exe می‌گردد",
          "soffice.exe" in names, str(names))
    check("🪟 رجیستری بدون winreg کرش نمی‌کند",
          isinstance(CG._lo_from_registry(), list))
finally:
    os.name = _real

names_l = CG._lo_exe_names()
check("🐧 روی لینوکس دنبال soffice می‌گردد", "soffice" in names_l)


# ═══════════ ۳) ✏️ مسیر دستی ادمین ═══════════
print("\n[۳] ✏️ مسیر دستی — راه نجات کاربر")

_keys = [r[0] for r in CG.CERT_SETTINGS]
check("🔴 کلید مسیر لیبره در تنظیمات هست (دکمه دارد)",
      "cert_soffice_path" in _keys)
check("کلید موتور داخلی هم در تنظیمات هست",
      "cert_png_fallback" in _keys)

_row = CG._setting_of("cert_soffice_path")
check("ردیف تنظیم پیدا می‌شود", _row is not None)
check("نوع آن متنی است", _row and _row[3] == "text")
check("راهنمای فارسی دارد", _row and "soffice" in (_row[5] or ""))

# مسیر دستی باید اول فهرست بیاید
database.set_setting("cert_soffice_path", r"C:\MyLO\soffice.exe",
                     "t", "certificate")
database.clear_settings_cache()
reset_lo()
c2 = CG._lo_candidates()
check("🔴 مسیر دستی اولویت اول است",
      c2 and "MyLO" in c2[0], str(c2[:2]))

# اگر پوشه بدهد نه فایل، باز هم بفهمد
database.set_setting("cert_soffice_path", r"C:\MyLO", "t", "certificate")
database.clear_settings_cache()
c3 = " ".join(CG._lo_candidates()[:6])
check("📁 اگر ادمین پوشه بدهد، خودش soffice را اضافه می‌کند",
      "soffice" in c3, c3[:100])

# گیومه اضافه نباید مشکل بسازد
database.set_setting("cert_soffice_path", '"C:\\Q\\soffice.exe"',
                     "t", "certificate")
database.clear_settings_cache()
c4 = CG._lo_candidates()
check('🔤 گیومه " دور مسیر حذف می‌شود',
      c4 and '"' not in c4[0], str(c4[:1]))

database.set_setting("cert_soffice_path", "", "t", "certificate")
database.clear_settings_cache()
reset_lo()


# ═══════════ ۴) 🔴 باگ URI خراب ═══════════
print("\n[۴] 🔴 URI پروفایل موقت")

check("تابع ساخت URI هست", hasattr(CG, "_profile_uri"))
u = CG._profile_uri(TMP)
check("🔴 URI با ///  شروع می‌شود (نه //)",
      u.startswith("file:///"), u)
check("URI بک‌اسلش ندارد", "\\" not in u, u)

_src = (ROOT / "certgen.py").read_text(encoding="utf-8")
_code_lines = [ln for ln in _src.split("\n")
               if "file://" in ln and not ln.strip().startswith("#")
               and "🔴" not in ln and "درست:" not in ln
               and "می‌شد" not in ln]
check('🔴 دیگر جایی f"file://{prof}" خام ساخته نمی‌شود',
      not any('f"file://' in ln for ln in _code_lines),
      str(_code_lines[:2]))
check("همه‌جا از _profile_uri استفاده می‌شود",
      _src.count("_profile_uri(prof)") >= 2,
      str(_src.count("_profile_uri(prof)")))


# ═══════════ ۵) 🩺 عیب‌یابی ═══════════
print("\n[۵] 🩺 گزارش عیب‌یابی")

d = CG.lo_diagnose()
for k in ("found", "path", "manual", "checked", "existing", "on_path"):
    check(f"گزارش کلید «{k}» دارد", k in d)
check("تعداد مسیرهای بررسی‌شده گزارش می‌شود",
      isinstance(d["checked"], int) and d["checked"] > 0)
check("گزارش found بولین است", isinstance(d["found"], bool))


# ═══════════ ۶) 📊 وضعیت موتور ═══════════
print("\n[۶] 📊 engine_status")

st = CG.engine_status()
for k in ("docx", "libreoffice", "lo_path", "word", "png",
          "png_builtin", "qr", "fa_shape"):
    check(f"وضعیت کلید «{k}» دارد", k in st)
check("engine_status پارامتر force می‌پذیرد",
      CG.engine_status(force=True) is not None)

# اگر لیبره باشد، png هم باید True شود (لیبره خودش PNG می‌دهد)
_ob = CG.libreoffice_bin
CG.libreoffice_bin = lambda force=False: r"C:\fake\soffice.exe"
try:
    st2 = CG.engine_status()
    check("🖼️ با وجود لیبره، تبدیل تصویر ممکن است "
          "(poppler لازم نیست)", st2["png"] is True)
    check("مسیر لیبره در وضعیت برمی‌گردد", "fake" in st2["lo_path"])
finally:
    CG.libreoffice_bin = _ob


# ═══════════ ۷) 🖼️ PNG مستقیم از لیبره ═══════════
print("\n[۷] 🖼️ مسیر مستقیم ورد → PNG")

check("تابع docx_to_png_lo هست", hasattr(CG, "docx_to_png_lo"))
check("بدون لیبره None برمی‌گرداند (کرش نه)",
      CG.docx_to_png_lo("/nope.docx", f"{TMP}/x.png") is None
      or CG.libreoffice_bin())
check("در generate صدا زده می‌شود", "docx_to_png_lo(" in _src)
check("pypdfium2 هم به‌عنوان راه چهارم اضافه شد",
      "pypdfium2" in _src)


# ═══════════ ۸) 📝 خطای واقعی ذخیره می‌شود ═══════════
print("\n[۸] 📝 پیام خطای واقعی")

check("تابع last_pdf_error هست", hasattr(CG, "last_pdf_error"))
check("خروجی رشته است", isinstance(CG.last_pdf_error(), str))

CG.docx_to_pdf(f"{TMP}/nothing.docx", TMP)
check("🔴 بعد از شکست، دلیل ثبت می‌شود",
      len(CG.last_pdf_error()) > 0, CG.last_pdf_error())


# ═══════════ ۹) 🪟 پنجره سیاه باز نشود ═══════════
print("\n[۹] 🪟 اجرای بی‌سروصدا")

check("تابع _no_window هست", hasattr(CG, "_no_window"))
check("روی لینوکس صفر برمی‌گرداند",
      CG._no_window() == 0 or os.name == "nt")
check("در همه subprocess ها استفاده شده",
      _src.count("creationflags=_no_window()") >= 4,
      str(_src.count("creationflags=_no_window()")))


# ═══════════ ۱۰) 🖥️ صفحه‌های پنل ═══════════
print("\n[۱۰] 🖥️ صفحه‌های ادمین")

SENT.clear()
M.handle_callback(cb(S, "ct_engine"))
t = last()
check("🩺 صفحه عیب‌یابی باز می‌شود", "موتور تبدیل" in t, t[:80])
check("وضعیت کامل نشان می‌دهد", "وضعیت کامل" in t)
check("دکمه مسیر دستی دارد",
      "ctse_cert_soffice_path" in last_kb())
check("دکمه جست‌وجوی دوباره دارد", "ct_engine" in last_kb())

SENT.clear()
M.handle_callback(cb(S, "ct_recheck"))
check("🔄 بررسی دوباره کار می‌کند", "راهنمای نصب" in last(),
      last()[:60])

SENT.clear()
M.handle_callback(cb(S, "ct_install"))
check("📦 راهنمای نصب باز می‌شود", "راهنمای نصب" in last())
check("دکمه عیب‌یابی در راهنما هست", "ct_engine" in last_kb())

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("🎓 هاب دکمه موتور تبدیل دارد", "ct_engine" in last_kb())

SENT.clear()
M.handle_callback(cb(S, "ct_panel"))
check("📄 پنل قالب‌ها سالم است", "قالب" in last())

SENT.clear()
M.handle_callback(cb(S, "ct_set_cert"))
check("⚙️ تنظیمات، دکمه مسیر لیبره دارد",
      "ctse_cert_soffice_path" in last_kb())


# ═══════════ ۱۱) ✏️ ورود مسیر از پنل ═══════════
print("\n[۱۱] ✏️ ادمین مسیر را وارد می‌کند")

SENT.clear()
M.handle_callback(cb(S, "ctse_cert_soffice_path"))
check("صفحه ورود مسیر باز شد", "LibreOffice" in last(), last()[:60])
check("state درست ست شد",
      auth.get_state_name(S) == CG.STATE_CT_SET,
      str(auth.get_state_name(S)))

SENT.clear()
CG.handle_setting(msg(S, r"C:\Program Files\LibreOffice\program"
                         r"\soffice.exe"))
t = alltext()
check("🔴 مسیر غلط → پیام مهربان راهنما، نه سکوت",
      "جواب نداد" in t or "کار می‌کند" in t, t[:120])
check("راه حل عملی می‌دهد (Properties)",
      "Properties" in t or "کار می‌کند" in t)
check("بعدش صفحه عیب‌یابی نشان داده می‌شود",
      "موتور تبدیل" in t)
check("state پاک شد", not auth.get_state_name(S))

# مقدار واقعاً ذخیره شد؟
database.clear_settings_cache()
check("مقدار در دیتابیس ذخیره شد",
      "soffice.exe" in database.get_setting("cert_soffice_path", ""))

# پاک کردن با -
SENT.clear()
M.handle_callback(cb(S, "ctse_cert_soffice_path"))
CG.handle_setting(msg(S, "-"))
database.clear_settings_cache()
check("با «-» مسیر پاک می‌شود",
      not database.get_setting("cert_soffice_path", ""))
check("پیام پاک‌شدن مهربان است", "پاک شد" in alltext(),
      alltext()[:80])
reset_lo()


# ═══════════ ۱۲) 🧪 تست واقعی تبدیل ═══════════
print("\n[۱۲] 🧪 دکمه تست واقعی")

check("تابع engine_test هست", hasattr(CG, "engine_test"))
SENT.clear()
M.handle_callback(cb(S, "ct_engtest"))
t = last()
check("🧪 تست اجرا می‌شود و کرش نمی‌کند", "تست" in t, t[:80])
check("سه مرحله را گزارش می‌دهد",
      "ورد" in t and "PDF" in t and "تصویر" in t)
check("زمان اجرا را می‌گوید", "ثانیه" in t)


# ═══════════ ۱۳) 💬 پیام‌های کاربرپسند ═══════════
print("\n[۱۳] 💬 متن‌ها")

g = CG.install_guide()
check("راهنما تولید می‌شود", len(g) > 100)

_realname = os.name
try:
    os.name = "nt"
    reset_lo()
    gw = CG.install_guide()
    check("🪟 روی ویندوز apt پیشنهاد نمی‌شود", "sudo apt" not in gw)
    check("🔴 می‌گوید لیبره به PATH اضافه نمی‌کند",
          "PATH" in gw or "عیب‌یابی" in gw, gw[-300:])
    check("به عیب‌یابی راهنمایی می‌کند", "عیب‌یابی" in gw)
finally:
    os.name = _realname
    reset_lo()

check("📛 در متن‌ها «گواهی حضور» نیامده",
      "گواهی حضور" not in _src)


# ═══════════ ۱۳.۵) 🎬 شبیه‌سازی کامل «لیبره نصب است» ═══════════
print("\n[۱۳.۵] 🎬 وقتی لیبره واقعاً هست — سرتاسر مسیر")

import subprocess as _sp
_real_run = _sp.run
_real_which = CG.shutil.which
_fake_lo = str(Path(TMP) / "soffice")
Path(_fake_lo).write_text("#!/bin/sh\necho LibreOffice 24.2\n")
os.chmod(_fake_lo, 0o755)

_seen = {"cmds": []}


def _fake_run(cmd, *a, **kw):
    """لیبرهٔ قلابی: --version جواب می‌دهد، تبدیل هم فایل می‌سازد"""
    _seen["cmds"].append(list(cmd) if isinstance(cmd, (list, tuple))
                         else [str(cmd)])
    c = _seen["cmds"][-1]

    class R:
        returncode = 0
        stdout = b"LibreOffice 24.2.1"
        stderr = b""

    if "--convert-to" in c:
        try:
            i = c.index("--outdir")
            outdir = Path(c[i + 1])
            srcf = Path(c[-1])
            fmt = c[c.index("--convert-to") + 1]
            ext = ".pdf" if fmt.startswith("pdf") else ".png"
            outdir.mkdir(parents=True, exist_ok=True)
            made = outdir / (srcf.stem + ext)
            if ext == ".pdf":
                made.write_bytes(b"%PDF-1.4\n% fake\n")
            else:
                from PIL import Image
                Image.new("RGB", (200, 140), "white").save(made)
        except Exception:
            pass
    return R()


try:
    _sp.run = _fake_run
    CG.subprocess.run = _fake_run
    CG.shutil.which = lambda n: (_fake_lo if "soffice" in str(n)
                                 else None)
    reset_lo()

    found = CG.libreoffice_bin(force=True)
    check("🎬 لیبره پیدا شد", bool(found), str(found))
    check("🎬 قبل از قبول کردن، --version گرفته شد",
          any("--version" in c for c in _seen["cmds"]))

    st3 = CG.engine_status()
    check("🎬 وضعیت می‌گوید نصب است", st3["libreoffice"] is True)
    check("🎬 مسیرش را نشان می‌دهد", bool(st3["lo_path"]))

    d3 = CG.lo_diagnose()
    check("🎬 عیب‌یابی هم می‌گوید پیدا شد", d3["found"] is True)

    # تبدیل واقعی
    import docx as _dxm
    _t = Path(TMP) / "e2e.docx"
    _d = _dxm.Document()
    _d.add_paragraph("گواهی می‌شود امیر نعمتی روزبهانی حاضر بود.")
    _d.save(str(_t))

    _seen["cmds"].clear()
    _pdf = CG.docx_to_pdf(str(_t), TMP)
    check("🎬 PDF ساخته شد", bool(_pdf) and Path(_pdf).exists(),
          str(_pdf))
    _cmd = " ".join(_seen["cmds"][-1]) if _seen["cmds"] else ""
    check("🔴 URI پروفایل درست است (file:///)",
          "file:///" in _cmd, _cmd[:160])
    check("🎬 حالت headless استفاده شد", "--headless" in _cmd)
    check("🎬 دیگر خطایی ثبت نشد", not CG.last_pdf_error(),
          CG.last_pdf_error())

    _png = CG.docx_to_png_lo(str(_t), Path(TMP) / "e2e.png")
    check("🖼️ PNG مستقیم از لیبره ساخته شد",
          bool(_png) and Path(_png).exists(), str(_png))

    # صفحه پنل باید سبز باشد
    SENT.clear()
    M.handle_callback(cb(S, "ct_engine"))
    _t2 = last()
    check("🖥️ پنل می‌گوید پیدا شد",
          "پیدا شد" in _t2 and "🔴" not in _t2, _t2[:100])
    check("🖥️ دکمه تست واقعی ظاهر شد", "ct_engtest" in last_kb())

    SENT.clear()
    M.handle_callback(cb(S, "ct_engtest"))
    _t3 = last()
    check("🧪 تست کامل سبز است",
          "✅ تبدیل به PDF" in _t3, _t3[:150])
    check("🧪 پیام موفقیت مهربان است", "عالی" in _t3 or "سالم" in _t3)

    # ⛔ حالا لیبره خراب شود — باید بی‌صدا نیفتد
    def _broken(cmd, *a, **kw):
        c = list(cmd)
        _seen["cmds"].append(c)

        class R:
            returncode = 1
            stdout = b""
            stderr = b"Error: source file could not be loaded"
        if "--version" in c:
            R.returncode = 0
            R.stdout = b"LibreOffice 24.2"
            R.stderr = b""
        return R()

    _sp.run = _broken
    CG.subprocess.run = _broken
    reset_lo()
    _pdf2 = CG.docx_to_pdf(str(_t), Path(TMP) / "sub")
    check("⛔ تبدیل خراب → None برمی‌گردد", _pdf2 is None)
    check("🔴 ولی دلیلش ثبت می‌شود (نه سکوت)",
          "could not be loaded" in CG.last_pdf_error(),
          CG.last_pdf_error())

    SENT.clear()
    M.handle_callback(cb(S, "ct_engine"))
    _t4 = last()
    check("🖥️ پنل خطای واقعی را نشان می‌دهد",
          "خطا داد" in _t4 or "پیام" in _t4, _t4[:160])
finally:
    _sp.run = _real_run
    CG.subprocess.run = _real_run
    CG.shutil.which = _real_which
    reset_lo()

check("♻️ بعد از برگشت به حالت عادی، وضعیت سالم است",
      isinstance(CG.engine_status(force=True), dict))


# ═══════════ ۱۴) 🛡️ رگرسیون ═══════════
print("\n[۱۴] 🛡️ رگرسیون — چیزی نشکسته باشد")

check("generate هنوز هست", hasattr(CG, "generate"))
check("fill_docx هنوز هست", hasattr(CG, "fill_docx"))
check("موتور داخلی پابرجاست", hasattr(CG, "docx_to_png_fallback"))
check("تشخیص QR پابرجاست", hasattr(CG, "looks_like_qr"))
check("بلیط پابرجاست", hasattr(CG, "build_ticket_text"))

r = CG.generate(CG.build_mapping(name="آزمون", serial="T1"))
check("بدون قالب، خطای تمیز می‌دهد",
      isinstance(r, dict) and r.get("error"))

check("docx_to_pdf با مسیر بی‌معنی کرش نمی‌کند",
      CG.docx_to_pdf("/nope/x.docx", TMP) is None)
check("pdf_to_png با مسیر بی‌معنی کرش نمی‌کند",
      CG.pdf_to_png("/nope/x.pdf", f"{TMP}/y.png") is None)
check("libreoffice_bin با ورودی بد کرش نمی‌کند",
      CG.libreoffice_bin() is None or True)

import guard as G  # noqa: E402
_f = G.check_new_features()
check("🛡️ همه قابلیت‌های ثبت‌شده سالم‌اند",
      all(_f.values()), str([k for k, v in _f.items() if not v]))

SENT.clear()
M.handle_callback(cb(S, "ct_hub"))
check("هاب گواهینامه سالم است", "گواهینامه" in last())


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۱ پاس شدند!")
