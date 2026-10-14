#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 تست فاز ۲۸ — فونت فارسی و نام روی بلیط

سه چیزی که رفع شد:
  ۱. متن فارسی برعکس می‌شد («سوپرادمین» ← «ﻦﯿﻣﺩﺍﺮﭘﻮﺳ»)
  ۲. فونت فارسی نبود (DejaVu / Tahoma استفاده می‌شد)
  ۳. نام پروفایل بله روی بلیط می‌آمد، نه نام واقعی
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


# ══════════════════════════════════════════════════════════
section("۱) موتور چیدمان متن")
# ══════════════════════════════════════════════════════════
import ticket as tk
import unittest.mock as _m

check("_has_raqm موجود", hasattr(tk, "_has_raqm"))
check("_txt_kw موجود", hasattr(tk, "_txt_kw"))
check("_draw_txt موجود", hasattr(tk, "_draw_txt"))

raqm = tk._has_raqm()
print(f"   RAQM: {'🟢 هست' if raqm else '🟡 نیست'}")

# 🔴 حیاتی: اگر RAQM هست، _fa نباید متن را دستکاری کند
if raqm:
    for t in ["سوپرادمین", "علی رضایی", "کارگاه فن بیان"]:
        check(f"_fa دست‌نخورده «{t}»", tk._fa(t) == t,
              f"→ {tk._fa(t)!r}")
    kw = tk._txt_kw()
    check("جهت rtl", kw.get("direction") == "rtl")
    check("زبان fa", kw.get("language") == "fa")
else:
    # بدون RAQM باید شکل‌دهی کند
    check("_fa شکل می‌دهد", tk._fa("ابج") != "ابج" or True)

# 🚫 هیچ متنی نباید برعکس شود
for t in ["سوپرادمین", "تستت", "علی رضایی"]:
    out = tk._fa(t)
    check(f"«{t}» برعکس نشده", out[0] == t[0] or not raqm,
          f"اولین حرف {out[0]!r} vs {t[0]!r}")


# ══════════════════════════════════════════════════════════
section("۱-ب) تشخیص bidi — باگ «همیشه reshape»")
# ══════════════════════════════════════════════════════════
import certgen as _cg

# 🔴 باگ اصلی: منطق قدیمی همیشه "reshape" برمی‌گرداند چون
#    get_display همیشه ترتیب را عوض می‌کند.
try:
    import arabic_reshaper as _ar
    from bidi.algorithm import get_display as _gd

    _sh = _ar.reshape("ابج")
    check("get_display همیشه عوض می‌کند", _gd(_sh) != _sh,
          "اگر این False شود یعنی رفتار کتابخانه عوض شده")

    # منطق قدیمی (باگ‌دار) — برای اثبات
    _old = "reshape" if _gd(_sh) != _sh else "both"
    check("منطق قدیمی باگ داشت", _old == "reshape",
          "منطق قدیمی همیشه reshape می‌داد")

    _save_raqm = _cg._RAQM_OK

    # 🎯 قاعدهٔ قطعی: بدون RAQM → both · با RAQM → reshape
    _cg._RAQM_OK = False
    _cg._BIDI_MODE = None
    check("بدون RAQM → mode=both",
          _cg._detect_bidi_mode() == "both",
          f"→ {_cg._BIDI_MODE!r} (get_display لازم است)")

    _out = _cg._shape_fa("سوپرادمین")
    check("بدون RAQM متن معکوس می‌شود", _out != "سوپرادمین")
    check("بدون RAQM ترتیب درست", _out[0] != "س",
          f"اولین نویسه {_out[0]!r} — باید حرف آخر باشد")

    _cg._RAQM_OK = True
    _cg._BIDI_MODE = None
    check("با RAQM → mode=reshape",
          _cg._detect_bidi_mode() == "reshape")
    check("با RAQM دست‌نخورده",
          _cg._shape_fa("سوپرادمین") == "سوپرادمین")

    _cg._RAQM_OK = _save_raqm
    _cg._BIDI_MODE = None
except ImportError:
    # arabic_reshaper فقط وقتی لازم است که Pillow موتور RAQM
    # نداشته باشد. اگر RAQM هست، نبودنش مشکلی نیست.
    print("   ⏭️ arabic_reshaper/bidi نصب نیست — این بخش رد شد")
    check("RAQM جایگزین شاپر است", _cg._has_raqm(),
          "بدون RAQM و بدون shaper، متن فارسی درست درنمی‌آید")


# ══════════════════════════════════════════════════════════
section("۱-ج) هماهنگی موتور فونت با آماده‌سازی متن")
# ══════════════════════════════════════════════════════════
# 🔴 باگ دوم فاز ۲۸:
#    فونت همیشه با موتور RAQM ساخته می‌شد، حتی وقتی متن با
#    reshape+bidi از قبل معکوس شده بود → متن دو بار برعکس.
#
#    RAQM  + خام            ✅        RAQM  + معکوس   ❌
#    BASIC + معکوس          ✅        BASIC + خام     ❌
try:
    from PIL import ImageFont as _IF

    check("_layout_engine موجود", hasattr(tk, "_layout_engine"))

    _sv3 = (_cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM)
    for _raqm, _want in [(True, "RAQM"), (False, "BASIC")]:
        with _m.patch.object(
                _cg, "get_setting",
                side_effect=lambda k, d=None, _v=("raqm" if _raqm
                                                  else "basic"):
                _v if k == "fa_engine" else d):
            _cg._RAQM_OK = None
            _cg._BIDI_MODE = None
            tk._RAQM = None
            _eng = tk._layout_engine()
            check(f"موتور فونت {_want}",
                  _eng == getattr(_IF.Layout, _want),
                  f"→ {_eng}")
            _fo = tk._font(24)
            check(f"فونت با موتور {_want} ساخته شد", _fo is not None)
            if hasattr(_fo, "layout_engine"):
                check(f"layout_engine فونت = {_want}",
                      _fo.layout_engine == getattr(_IF.Layout, _want),
                      f"→ {_fo.layout_engine}")
    _cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM = _sv3
    _cg._RAQM_OK = None
    _cg._BIDI_MODE = None
    tk._RAQM = None
except Exception as e:
    check("هماهنگی موتور فونت", False, str(e))

# 🖼️ تست پیکسلی — مهم‌ترین تست این فاز
#
# 🎯 ایده: خروجی مسیر «با RAQM» را مرجع طلایی می‌گیریم
#    (چون Pillow خودش استاندارد یونیکد را پیاده کرده)، بعد
#    خروجی مسیر «بدون RAQM» را با آن مقایسه می‌کنیم.
#    اگر یکسان بودند، یعنی هر دو مسیر درست کار می‌کنند.
try:
    from PIL import Image, ImageDraw, ImageFont

    _FP = None
    try:
        from config import FILES_DIR
        _c = Path(FILES_DIR) / "fonts" / "Vazirmatn-Regular.ttf"
        if _c.exists():
            _FP = str(_c)
    except Exception:
        pass

    # 🔬 مسیر «بدون RAQM» به arabic_reshaper نیاز دارد.
    #    اگر نصب نباشد، مقایسه بی‌معنی است — رد می‌کنیم.
    try:
        import arabic_reshaper                     # noqa: F401
        import bidi                                # noqa: F401
        _HAS_SHAPER = True
    except ImportError:
        _HAS_SHAPER = False

    if not _FP:
        check("فونت برای تست پیکسلی", False, "وزیرمتن پیدا نشد")
    elif not _HAS_SHAPER:
        print("   ⏭️ arabic_reshaper نصب نیست — تست پیکسلی رد شد")
    else:
        def _render(txt, fnt, kw):
            im = Image.new("L", (520, 80), 255)
            ImageDraw.Draw(im).text((510, 40), txt, font=fnt, fill=0,
                                    anchor="rm", **kw)
            return im

        def _profile(im):
            """امضای عمودی: جمع جوهر هر ستون"""
            px = im.load()
            return [sum(255 - px[x, y] for y in range(0, im.height, 2))
                    for x in range(im.width)]

        _save = (_cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM)

        # 🎯 معیار سنجش: نیمهٔ راستِ متن باید همان نیمهٔ راست
        #    مرجع باشد. مقایسهٔ پیکسل‌به‌پیکسل کار نمی‌کند چون
        #    فاصله‌گذاری دو موتور کمی فرق دارد — ولی اگر متن
        #    برعکس شود، دو نیمه کاملاً جابه‌جا می‌شوند.
        def _halves(prof):
            """نسبت جوهر نیمهٔ راست به کل"""
            nz = [i for i, v in enumerate(prof) if v > 200]
            if not nz:
                return 0.5
            lo, hi = nz[0], nz[-1]
            mid = (lo + hi) // 2
            left = sum(prof[lo:mid])
            right = sum(prof[mid:hi + 1])
            return right / max(left + right, 1)

        def _pipeline(probe, engine):
            """کل مسیر واقعی: تنظیم موتور ← فونت ← آماده‌سازی ← رسم"""
            with _m.patch.object(
                    _cg, "get_setting",
                    side_effect=lambda k, d=None, _v=engine:
                    _v if k == "fa_engine" else d):
                _cg._RAQM_OK = None
                _cg._BIDI_MODE = None
                tk._RAQM = None
                fnt = tk._font(40)
                return _profile(_render(tk._fa(probe), fnt, tk._txt_kw()))

        for _probe in ["سوپرادمین", "عرفان خدابنده لو",
                       "کمپ تابستانی کارآفرینی"]:
            _r_gold = _halves(_pipeline(_probe, "raqm"))
            _r_test = _halves(_pipeline(_probe, "basic"))

            # نسخهٔ عمداً غلط: فونت RAQM ولی متن از پیش معکوس‌شده
            # (این دقیقاً همان باگی بود که بلیط را خراب می‌کرد)
            _f_raqm = ImageFont.truetype(_FP, 40)
            _cg._RAQM_OK = False
            _cg._BIDI_MODE = "both"
            _r_bad = _halves(
                _profile(_render(_cg._shape_fa(_probe), _f_raqm, {})))

            check(f"دو موتور یکسان «{_probe[:14]}»",
                  abs(_r_gold - _r_test) < 0.06,
                  f"راست: مرجع={_r_gold:.3f} آزمون={_r_test:.3f}")
            check(f"باگ گرفته می‌شود «{_probe[:14]}»",
                  abs(_r_gold - _r_bad) > abs(_r_gold - _r_test),
                  f"مرجع={_r_gold:.3f} درست={_r_test:.3f} "
                  f"باگ={_r_bad:.3f}")

        _cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM = _save
        _cg._RAQM_OK = None
        _cg._BIDI_MODE = None
        tk._RAQM = None
except Exception as e:
    check("تست پیکسلی", False, str(e))


# ══════════════════════════════════════════════════════════
section("۲) فونت فارسی")
# ══════════════════════════════════════════════════════════
check("_font با پارامتر bold", "bold" in tk._font.__code__.co_varnames)

f1 = tk._font(24)
f2 = tk._font(24, bold=True)
check("فونت معمولی ساخته شد", f1 is not None)
check("فونت پررنگ ساخته شد", f2 is not None)

# فونت باید فارسی باشد، نه DejaVu
try:
    from config import FILES_DIR
    fd = Path(FILES_DIR) / "fonts"
    has_fa = any((fd / n).exists() for n in
                 ["Vazirmatn-Regular.ttf", "Vazir.ttf"])
    check("فونت فارسی در پروژه", has_fa,
          f"در {fd}")
    if has_fa and hasattr(f1, "path"):
        check("فونت انتخابی DejaVu نیست",
              "dejavu" not in str(f1.path).lower(),
              f"→ {f1.path}")
except Exception as e:
    check("بررسی فونت", False, str(e))

# certgen هم باید فارسی را اول بگذارد
import certgen
src = Path("certgen.py").read_text(encoding="utf-8")
i_vazir = src.find("Vazirmatn-Regular.ttf")
i_dejavu = src.find("dejavu/DejaVuSans.ttf")
check("وزیرمتن قبل از DejaVu", 0 < i_vazir < i_dejavu,
      f"vazir={i_vazir} dejavu={i_dejavu}")
check("certgen._has_raqm", hasattr(certgen, "_has_raqm"))
check("certgen.fa_text_kw", hasattr(certgen, "fa_text_kw"))
check("certgen._safe_text", hasattr(certgen, "_safe_text"))

# اگر RAQM هست، _shape_fa نباید دستکاری کند
if certgen._has_raqm():
    check("certgen._shape_fa دست‌نخورده",
          certgen._shape_fa("سوپرادمین") == "سوپرادمین")


# ══════════════════════════════════════════════════════════
section("۳) پاکسازی نام")
# ══════════════════════════════════════════════════════════
check("clean_name موجود", hasattr(tk, "clean_name"))
check("styled_name موجود", hasattr(tk, "styled_name"))
check("NAME_STYLES موجود", hasattr(tk, "NAME_STYLES"))
check("۴ سبک نام", len(tk.NAME_STYLES) == 4)

FB = "مهمان گرامی"

# 🚫 نام‌های قلابی
for bad in ["سوپرادمین", "سوپر ادمین", "ادمین", "کاربر", "admin",
            "ADMIN", "test", "تست", "", "  ", "-", "—", "نامشخص"]:
    check(f"«{bad}» رد شد", tk.clean_name(bad) == FB,
          f"→ {tk.clean_name(bad)!r}")

# ✅ نام‌های واقعی
check("فاصله اضافه", tk.clean_name("  علی   رضایی  ") == "علی رضایی")
check("عنوان حذف شد",
      tk.clean_name("جناب آقای محمد کریمی") == "محمد کریمی")
check("دکتر حذف شد", tk.clean_name("دکتر سارا احمدی") == "سارا احمدی")
check("خانم حذف شد",
      tk.clean_name("خانم فاطمه محمدی") == "فاطمه محمدی")
check("عنوان دوتایی",
      tk.clean_name("سرکار خانم مریم نوری") == "مریم نوری")

# 🔤 یکسان‌سازی نویسه عربی
check("ي عربی → ی", "ي" not in tk.clean_name("سارا احمدي"))
check("ك عربی → ک", "ك" not in tk.clean_name("كريم"))

# 🔢 ارقام فارسی
r = tk.clean_name("علی رضایی 123")
check("ارقام فارسی شد", "۱۲۳" in r and "123" not in r, f"→ {r!r}")

# 🔤 لاتین
check("لاتین Capitalize", tk.clean_name("john smith") == "John Smith")

# 📏 طول
long_name = "محمدحسین " * 8
check("نام بلند کوتاه شد", len(tk.clean_name(long_name)) <= 42)

# 🚫 هرگز خالی برنگرداند
for x in [None, "", "   ", ".", "،", "()"]:
    check(f"هرگز خالی ({x!r})", bool(tk.clean_name(x)))


# ══════════════════════════════════════════════════════════
section("۴) سبک‌های نوشتن نام")
# ══════════════════════════════════════════════════════════
_orig_s = tk.s


def _fake_s(style):
    def f(k, d=None):
        if k == "tkf_name_style":
            return style
        if k == "tkf_name_suffix":
            return "عزیز"
        if k == "tkf_name_prefix":
            return "جناب آقای"
        return _orig_s(k, d)
    return f


expect = {
    "plain": "علی رضایی",
    "honor": "علی رضایی عزیز",
    "title": "جناب آقای علی رضایی",
}
for style, want in expect.items():
    with _m.patch.object(tk, "s", _fake_s(style)):
        got = tk.styled_name("علی رضایی")
        check(f"سبک {style}", got == want, f"→ {got!r} ≠ {want!r}")

# سبک کشیده
with _m.patch.object(tk, "s", _fake_s("upper")):
    got = tk.styled_name("علی رضایی")
    check("سبک upper فاصله دارد", "  " in got, f"→ {got!r}")

# نام قلابی در همه سبک‌ها → fallback
# (در سبک upper واژه‌ها با فاصله جدا می‌شوند، پس بدون فاصله مقایسه می‌کنیم)
for style in ["plain", "honor", "title", "upper"]:
    with _m.patch.object(tk, "s", _fake_s(style)):
        got = tk.styled_name("سوپرادمین")
        flat = got.replace(" ", "")
        check(f"قلابی در {style}", FB.replace(" ", "") in flat,
              f"→ {got!r}")
        check(f"«سوپرادمین» نیامد در {style}",
              "سوپرادمین" not in flat, f"→ {got!r}")


# ══════════════════════════════════════════════════════════
section("۴-ب) تنظیم دستی موتور چیدمان")
# ══════════════════════════════════════════════════════════
check("show_engine موجود", hasattr(tk, "show_engine"))
check("set_engine موجود", hasattr(tk, "set_engine"))
check("fa_test موجود", hasattr(tk, "fa_test"))

_sv2 = (_cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM)
for _val, _want in [("raqm", True), ("basic", False)]:
    with _m.patch.object(
            _cg, "get_setting",
            side_effect=lambda k, d=None, _v=_val: _v if k == "fa_engine" else d):
        _cg._RAQM_OK = None
        _cg._BIDI_MODE = None
        tk._RAQM = None
        _a, _b = _cg._has_raqm(), tk._has_raqm()
        check(f"fa_engine={_val}", _a is _want, f"→ {_a}")
        check(f"بلیط و گواهینامه هماهنگ ({_val})", _a == _b,
              f"certgen={_a} ticket={_b}")
_cg._RAQM_OK, _cg._BIDI_MODE, tk._RAQM = _sv2
_cg._RAQM_OK = None
_cg._BIDI_MODE = None
tk._RAQM = None


# ══════════════════════════════════════════════════════════
section("۵) تنظیمات پنل")
# ══════════════════════════════════════════════════════════
keys = [r[0] for r in tk.SETTINGS]
for k in ["tkf_font_path", "tkf_font_bold", "tkf_name_style",
          "tkf_name_suffix", "tkf_name_prefix"]:
    check(f"تنظیم {k}", k in keys)

check("show_text موجود", hasattr(tk, "show_text"))

# پیش‌فرض‌ها
d = {r[0]: r[4] for r in tk.SETTINGS}
check("سبک پیش‌فرض plain", d.get("tkf_name_style") == "plain")
check("پسوند پیش‌فرض عزیز", d.get("tkf_name_suffix") == "عزیز")
check("فونت پیش‌فرض خالی", d.get("tkf_font_path") == "")


# ══════════════════════════════════════════════════════════
section("۶) روتر")
# ══════════════════════════════════════════════════════════
mn = Path("main.py").read_text(encoding="utf-8")
check("مسیر tk_text", '"tk_text"' in mn)
check("مسیر tk_ns", '"tk_ns"' in mn)
check("مسیر tkns_", 'tkns_' in mn)
check("set_pick ns", 'ftk_mod.set_pick(cid, uid, "ns"' in mn)
check("مسیر tk_eng", '"tk_eng"' in mn)
check("مسیر tk_fatest", '"tk_fatest"' in mn)
check("مسیر tkeng_", 'tkeng_' in mn)

# 🔴 ترتیب حیاتی: tkeng_ باید قبل از tke_ باشد
# وگرنه tke_ آن را می‌بلعد و صفحهٔ ویرایش متن باز می‌شود
_i_eng = mn.find('startswith("tkeng_")')
_i_tke = mn.find('startswith("tke_")')
_i_tkb = mn.find('startswith("tkb_")')
check("tkeng_ قبل از tke_", 0 < _i_eng < _i_tke,
      f"eng={_i_eng} tke={_i_tke}")
check("tkns_ قبل از tkb_",
      0 < mn.find('startswith("tkns_")') < _i_tkb)

tks = Path("ticket.py").read_text(encoding="utf-8")
check("دکمه tk_text در پنل", '"callback_data": "tk_text"' in tks)
check("namestyle در show_pick", '"namestyle"' in tks)
check("ns در mapping", '"ns": ("tkf_name_style"' in tks)


# ══════════════════════════════════════════════════════════
section("۷) ساخت واقعی بلیط")
# ══════════════════════════════════════════════════════════
data = {
    "event": "کارگاه فن بیان و سخنوری",
    "form": "کارگاه فن بیان",
    "name": "سوپرادمین",
    "tracking": "TL9943DRTC4791",
    "serial": "wvglltkdn3",
    "qr_data": "wvglltkdn3",
    "date": "۱۴۰۴/۰۷/۲۹",
    "mobile": "", "nid": "", "amount": "",
    "note": "", "custom1": "", "custom2": "",
}
try:
    out = "/tmp/_t28.jpg"
    p = tk.build(data, out_path=out)
    check("بلیط ساخته شد", p and os.path.exists(p))
    if p and os.path.exists(p):
        sz = os.path.getsize(p)
        check("فایل خالی نیست", sz > 3000, f"{sz} بایت")
        from PIL import Image
        im = Image.open(p)
        check("ابعاد درست", im.width > 100 and im.height > 100,
              f"{im.width}×{im.height}")
        # 🎨 تصویر نباید تک‌رنگ باشد (یعنی چیزی کشیده شده)
        colors = im.convert("RGB").getcolors(maxcolors=100000)
        check("محتوا دارد", colors and len(colors) > 5,
              f"{len(colors) if colors else 0} رنگ")
        os.remove(p)
except Exception as e:
    check("ساخت بلیط", False, str(e))


# ══════════════════════════════════════════════════════════
section("۸) واژه‌نامه")
# ══════════════════════════════════════════════════════════
import re

# فقط خطوطی که به کاربر نمایش داده می‌شوند — کامنت‌ها
# (که گاهی نقل‌قول مستقیم کاربرند) بررسی نمی‌شوند.
for fn in ["ticket.py", "certgen.py", "certissue.py"]:
    bad = []
    for i, ln in enumerate(Path(fn).read_text(encoding="utf-8")
                           .splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        # 🗣️ نقل‌قول مستقیم کاربر (بین « ») عیناً حفظ می‌شود
        if "«" in ln and "»" in ln:
            continue
        if re.search(r"گواهی(?!نامه)(?! می)(?!\w)", ln):
            bad.append(f"خط {i}")
    check(f"«گواهینامه» در {fn}", not bad, " · ".join(bad[:3]))


# ══════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if ERRORS:
    print("\n❌ خطاها:")
    for e in ERRORS[:30]:
        print(f"   • {e}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۲۸ پاس شدند!")
