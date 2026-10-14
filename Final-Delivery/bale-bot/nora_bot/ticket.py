"""
🎫 بلیط فرم — فاز ۲۶

درخواست کاربر (عیناً):
  «بریم سراغ بلیط. این بلیط دیجی‌فرمه، یه چیز ساده مثل بساز با
   ویژگی‌های این بلیط، فقط برای فرم فعال باشه: اسم رویداد، اسم شخص
   تکمیل‌کننده، کیوآرکد و شماره ثبت زیرش. اینو تو پنل مرتبط با بلیط
   قابل کم و زیاد و اضافه کردن باشه و هرچیزی که فکر میکنی نیازه با
   هر جزییاتی بهش اضافه کن. بلیط لازم نیست کپی این باشه.
   لوگو ربات رو من میفرستم بعدا تو قسمت مدیریت بلیط، یه گوشه بلیط
   لوگو ربات باشه در هر بلیط. قالب بلیط هم یه چیز ساده مثل و فقط یه
   بک‌گراند رنگی و یه چیز کوچیک باشه. کلا بک‌گراندش رو بتونم اضافه
   کنم با تنظیم سایز بلیط»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧱 معماری: بلیط از «بلوک» ساخته می‌شود

  هر بلوک یک ردیف است که ادمین می‌تواند:
     • روشن/خاموش کند
     • بالا و پایین ببرد
     • اندازه و رنگ متنش را عوض کند
     • برچسبش را بازنویسی کند

  ترتیب پیش‌فرض (مثل نمونه دیجی‌فرم):
     🏷️ نوار عنوان (نام رویداد)
     👤 نام شخص تکمیل‌کننده
     🔖 کد پیگیری
     🔳 کیوآرکد
     #️⃣ شماره ثبت (زیر کیوآر)

  و بلوک‌های اختیاری: تاریخ · موبایل · کد ملی · مبلغ · مکان ·
  یادداشت · پانویس · هر متن دلخواه

🖼️ پس‌زمینه: رنگ ساده یا تصویر آپلودی
🏛️ لوگو: در هر گوشه‌ای که بخواهید
📐 اندازه: از پیش‌فرض‌ها یا دلخواه
"""
from privacy import user_error_message
import json
import time
from pathlib import Path

from config import FILES_DIR
from database import db_execute, get_setting, set_setting, log

TICKET_DIR = Path(FILES_DIR) / "tickets"
TICKET_ASSET_DIR = Path(FILES_DIR) / "ticket_assets"

STATE_TK_SET = "tk_set"
STATE_TK_ASSET = "tk_asset"


# ══════════════════════════════════════════════════════════
# 🧱 بلوک‌های بلیط
#
# (کلید, آیکن, نام, پیش‌فرض روشن؟, برچسب پیش‌فرض)
# ══════════════════════════════════════════════════════════
BLOCKS = [
    ("header",   "🏷️", "نوار عنوان (نام رویداد)", 1, ""),
    ("name",     "👤", "نام تکمیل‌کننده",          1, ""),
    ("tracking", "🔖", "کد پیگیری",                1, "کد پیگیری:"),
    ("qr",       "🔳", "کیوآرکد",                  1, ""),
    ("serial",   "#️⃣", "شماره ثبت (زیر کیوآر)",    1, ""),
    ("form",     "📋", "نام فرم",                  0, "فرم:"),
    ("date",     "📅", "تاریخ ثبت",                0, "تاریخ:"),
    ("mobile",   "📱", "موبایل",                   0, "موبایل:"),
    ("nid",      "🆔", "کد ملی",                   0, "کد ملی:"),
    ("amount",   "💰", "مبلغ پرداختی",             0, "مبلغ:"),
    ("place",    "📍", "مکان",                     0, "مکان:"),
    ("note",     "📝", "یادداشت",                  0, ""),
    ("footer",   "🏛️", "پانویس",                   0, ""),
    ("custom1",  "✏️", "متن دلخواه ۱",             0, ""),
    ("custom2",  "✏️", "متن دلخواه ۲",             0, ""),
]

BLOCK_KEYS = [b[0] for b in BLOCKS]

# 📐 اندازه‌های آماده
SIZES = {
    "portrait":  ("📱 عمودی (۶۰۰×۸۰۰)", 600, 800),
    "square":    ("⬜ مربع (۸۰۰×۸۰۰)", 800, 800),
    "landscape": ("🖥️ افقی (۱۰۰۰×۶۰۰)", 1000, 600),
    "story":     ("📲 استوری (۱۰۸۰×۱۹۲۰)", 1080, 1920),
    "card":      ("💳 کارتی (۸۵۶×۵۴۰)", 856, 540),
    "custom":    ("✏️ دلخواه", 0, 0),
}

# 🎨 پالت‌های آماده — (نام, پس‌زمینه, نوار, متن نوار)
PALETTES = {
    "cream":  ("🍦 کرم و طلایی", "#FBF8C8", "#C9A84C", "#FFFFFF"),
    "mint":   ("🌿 سبز نعنایی", "#E8F6EF", "#2E8B67", "#FFFFFF"),
    "sky":    ("🌤️ آبی آسمانی", "#E9F2FB", "#2C6FB5", "#FFFFFF"),
    "rose":   ("🌸 صورتی", "#FDEEF3", "#C85A8C", "#FFFFFF"),
    "sand":   ("🏜️ شنی", "#F7F1E6", "#8C6B3F", "#FFFFFF"),
    "night":  ("🌙 شب", "#22283A", "#4A5578", "#FFFFFF"),
    "custom": ("✏️ دلخواه", "", "", ""),
}

LOGO_POS = {
    "tl": "↖️ بالا چپ", "tr": "↗️ بالا راست",
    "bl": "↙️ پایین چپ", "br": "↘️ پایین راست",
    "tc": "⬆️ بالا وسط", "bc": "⬇️ پایین وسط",
}


# ══════════════════════════════════════════════════════════
# ⚙️ تنظیمات
# (کلید, آیکن, نام, نوع, پیش‌فرض, راهنما)
# ══════════════════════════════════════════════════════════
SETTINGS = [
    ("tkf_on", "🎫", "بلیط تصویری فرم", "bool", "1",
     "بعد از تکمیل فرم، تصویر بلیط فرستاده شود"),
    ("tkf_size", "📐", "اندازه بلیط", "pick", "portrait", ""),
    ("tkf_w", "↔️", "پهنا (پیکسل)", "num", "600", "فقط در حالت دلخواه"),
    ("tkf_h", "↕️", "بلندا (پیکسل)", "num", "800", "فقط در حالت دلخواه"),
    ("tkf_palette", "🎨", "رنگ‌بندی", "pick", "cream", ""),
    ("tkf_bg", "🎨", "رنگ پس‌زمینه", "text", "#FBF8C8", "کد رنگ #RRGGBB"),
    ("tkf_band", "🎀", "رنگ نوار عنوان", "text", "#C9A84C", ""),
    ("tkf_band_text", "🔤", "رنگ متن نوار", "text", "#FFFFFF", ""),
    ("tkf_text", "🖋️", "رنگ متن اصلی", "text", "#333333", ""),
    ("tkf_band_h", "📏", "ارتفاع نوار (٪)", "num", "12",
     "درصدی از بلندای بلیط"),
    ("tkf_corner", "🔵", "گوشهٔ تزئینی پایین", "bool", "1",
     "کمان نرم پایین بلیط"),
    ("tkf_align", "📐", "چیدمان عمودی", "pick", "spread",
     "spread: پخش · center: وسط · top: از بالا"),
    ("tkf_gap", "↕️", "فاصله سطرها (٪)", "num", "3",
     "درصدی از بلندای بلیط"),
    ("tkf_border", "🖼️", "کادر دور بلیط", "bool", "0", ""),
    ("tkf_bgimg_mode", "🌄", "حالت تصویر پس‌زمینه", "pick", "cover",
     "cover: پر کند · fit: جا شود · tile: تکرار"),
    ("tkf_logo_pos", "🏛️", "جای لوگو", "pick", "tr", ""),
    ("tkf_logo_size", "📐", "اندازه لوگو (٪)", "num", "12",
     "درصدی از پهنای بلیط"),
    ("tkf_logo_pad", "↔️", "فاصله لوگو از لبه", "num", "18", "پیکسل"),
    ("tkf_qr_size", "🔳", "اندازه کیوآر (٪)", "num", "30",
     "درصدی از پهنای بلیط"),
    ("tkf_qr_frame", "⬜", "قاب سفید دور کیوآر", "bool", "1", ""),
    ("tkf_note_text", "📝", "متن یادداشت", "text",
     "لطفاً این بلیط را همراه داشته باشید 💚", ""),
    ("tkf_footer_text", "🏛️", "متن پانویس", "text", "", ""),
    ("tkf_custom1", "✏️", "متن دلخواه ۱", "text", "", ""),
    ("tkf_custom2", "✏️", "متن دلخواه ۲", "text", "", ""),
    ("tkf_keep_hours", "⏰", "نگهداری فایل (ساعت)", "num", "48",
     "۰ = برای همیشه"),
    # ── 🔤 فونت و نام ──────────────────────────────────
    ("tkf_font_path", "🔤", "فونت فارسی", "text", "",
     "مسیر فایل ttf — خالی = وزیرمتن"),
    ("tkf_font_bold", "🅱️", "فونت عنوان (پررنگ)", "text", "",
     "مسیر ttf پررنگ — خالی = وزیرمتن Bold"),
    ("tkf_name_style", "👤", "سبک نوشتن نام", "pick", "plain",
     "plain: ساده · honor: با «عزیز» · title: با آقای/خانم"),
    ("tkf_name_suffix", "💚", "عبارت بعد از نام", "text", "عزیز",
     "فقط در سبک «با عزیز»"),
    ("tkf_name_prefix", "🎗️", "عبارت پیش از نام", "text", "",
     "مثلاً «جناب آقای» — فقط در سبک عنوان‌دار"),
]

# 👤 سبک‌های نوشتن نام
NAME_STYLES = [
    ("plain", "ساده", "علی رضایی"),
    ("honor", "با عبارت احترام", "علی رضایی عزیز"),
    ("title", "با عنوان", "جناب آقای علی رضایی"),
    ("upper", "درشت و جدا", "ع ل ی   ر ض ا ی ی"),
]


def _srow(key):
    for r in SETTINGS:
        if r[0] == key:
            return r
    return None


def s(key, dflt=None):
    r = _srow(key)
    return get_setting(key, dflt if dflt is not None
                       else (r[4] if r else ""))


def s_on(key):
    return s(key) == "1"


def s_num(key, dflt=0):
    try:
        return int(float(s(key) or dflt))
    except (TypeError, ValueError):
        return int(dflt)


def enabled():
    return s_on("tkf_on")


# ─────────── چیدمان بلوک‌ها ───────────
def _layout_raw():
    raw = get_setting("tkf_layout", "")
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, list):
                return v
        except (ValueError, TypeError):
            pass
    return None


def layout():
    """
    🧱 چیدمان فعلی بلیط.

    خروجی: [{"key","on","size","label"}]
    """
    saved = {x.get("key"): x for x in (_layout_raw() or [])
             if isinstance(x, dict)}
    order = [x.get("key") for x in (_layout_raw() or [])
             if isinstance(x, dict) and x.get("key") in BLOCK_KEYS]
    for k in BLOCK_KEYS:
        if k not in order:
            order.append(k)
    out = []
    for k in order:
        b = next((x for x in BLOCKS if x[0] == k), None)
        if not b:
            continue
        old = saved.get(k) or {}
        out.append({
            "key": k,
            "on": int(old.get("on", b[3])),
            "size": int(old.get("size", _def_size(k))),
            "label": old.get("label", b[4]),
        })
    return out


def _def_size(key):
    return {"header": 34, "name": 30, "tracking": 22, "serial": 20,
            "note": 16, "footer": 15}.get(key, 18)


def save_layout(items, uid=None):
    set_setting("tkf_layout", json.dumps(items, ensure_ascii=False),
                "چیدمان بلیط", "ticket", uid)


def block_of(key):
    return next((b for b in layout() if b["key"] == key), None)


def block_meta(key):
    return next((b for b in BLOCKS if b[0] == key), None)


def toggle_block(key, uid=None):
    items = layout()
    for it in items:
        if it["key"] == key:
            it["on"] = 0 if it["on"] else 1
    save_layout(items, uid)


def move_block(key, delta, uid=None):
    items = layout()
    idx = next((i for i, x in enumerate(items) if x["key"] == key), None)
    if idx is None:
        return
    new = idx + delta
    if not (0 <= new < len(items)):
        return
    items[idx], items[new] = items[new], items[idx]
    save_layout(items, uid)


def set_block_field(key, field, value, uid=None):
    items = layout()
    for it in items:
        if it["key"] == key:
            it[field] = value
    save_layout(items, uid)


def reset_layout(uid=None):
    set_setting("tkf_layout", "", "چیدمان بلیط", "ticket", uid)


# ─────────── 🖼️ دارایی‌ها (لوگو / پس‌زمینه) ───────────
def asset_path(kind):
    """kind: logo | bg"""
    p = (get_setting(f"tkf_asset_{kind}", "") or "").strip()
    if p and Path(p).exists():
        return p
    return ""


def set_asset(kind, path, uid=None):
    set_setting(f"tkf_asset_{kind}", str(path or ""),
                f"تصویر بلیط {kind}", "ticket", uid)


def del_asset(kind, uid=None):
    p = asset_path(kind)
    if p:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
    set_setting(f"tkf_asset_{kind}", "", f"تصویر بلیط {kind}",
                "ticket", uid)


# ─────────── 🎨 کمکی‌های رنگ ───────────
def _hex(c, dflt=(255, 255, 255)):
    try:
        t = str(c or "").strip().lstrip("#")
        if len(t) == 3:
            t = "".join(ch * 2 for ch in t)
        if len(t) != 6:
            return dflt
        return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return dflt


def palette():
    """🎨 رنگ‌های فعلی — از پالت آماده یا دلخواه"""
    p = s("tkf_palette", "cream")
    if p in PALETTES and p != "custom":
        _n, bg, band, bt = PALETTES[p]
        return (_hex(bg), _hex(band), _hex(bt),
                _hex(s("tkf_text", "#333333")))
    return (_hex(s("tkf_bg", "#FBF8C8")),
            _hex(s("tkf_band", "#C9A84C")),
            _hex(s("tkf_band_text", "#FFFFFF")),
            _hex(s("tkf_text", "#333333")))


def size_wh():
    """📐 پهنا و بلندای بلیط"""
    k = s("tkf_size", "portrait")
    if k in SIZES and k != "custom":
        return SIZES[k][1], SIZES[k][2]
    w = max(200, min(3000, s_num("tkf_w", 600)))
    h = max(200, min(3000, s_num("tkf_h", 800)))
    return w, h


# ══════════════════════════════════════════════════════════
# 👤 پاکسازی نام
# ══════════════════════════════════════════════════════════

# 🚫 نام‌هایی که نام واقعی نیستند — نباید روی بلیط بیایند
_FAKE_NAMES = {
    "سوپرادمین", "سوپر ادمین", "ادمین", "مدیر", "کاربر",
    "admin", "superadmin", "super admin", "user", "guest",
    "test", "تست", "بدون نام", "نامشخص", "-", "—", ".",
}

# ✂️ پیشوند و پسوندهایی که در نوشتن رسمی حذف می‌شوند
_TITLES = (
    "جناب آقای", "سرکار خانم", "جناب", "سرکار",
    "آقای", "خانم", "دکتر", "مهندس", "استاد",
    "حاج آقا", "حاجی", "سید", "سیده",
)


def clean_name(raw, fallback="مهمان گرامی"):
    """
    ✨ مرتب کردن نام برای نمایش روی بلیط.

    کارهایی که می‌کند:
      • فاصله‌های اضافه و نیم‌فاصله‌های خراب را درست می‌کند
      • «سوپرادمین» و امثالش را نام واقعی حساب نمی‌کند
      • عناوین (آقای، دکتر…) را برمی‌دارد
      • ارقام لاتین را فارسی می‌کند
      • حرف اول هر واژه را بزرگ می‌کند (برای نام لاتین)
      • اگر خیلی بلند بود، کوتاه می‌کند
    """
    t = str(raw or "").strip()
    if not t:
        return fallback

    # 🧹 یکسان‌سازی نویسه‌های عربی و فاصله‌ها
    t = (t.replace("ي", "ی").replace("ك", "ک")
          .replace("ة", "ه").replace("ۀ", "هٔ")
          .replace("\u200c\u200c", "\u200c")
          .replace("\t", " ").replace("\n", " "))
    t = " ".join(t.split())
    t = t.strip(" .،,;:-_|/\\\"'()[]{}")

    if not t or t.lower() in _FAKE_NAMES or t in _FAKE_NAMES:
        return fallback

    # ✂️ حذف عنوان از ابتدا
    changed = True
    while changed:
        changed = False
        for ttl in _TITLES:
            if t.startswith(ttl + " "):
                t = t[len(ttl):].strip()
                changed = True
    if not t or t in _FAKE_NAMES:
        return fallback

    # 🔤 نام لاتین → حرف اول بزرگ
    if all(ord(c) < 128 for c in t.replace(" ", "")):
        t = " ".join(w.capitalize() for w in t.split())

    # 🔢 ارقام لاتین → فارسی
    t = t.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

    # 📏 خیلی بلند نباشد
    if len(t) > 42:
        parts = t.split()
        t = " ".join(parts[:3]) if len(parts) > 3 else t[:42].strip()

    return t or fallback


def styled_name(raw):
    """
    🎨 نام را با سبک انتخابی کاربر آماده می‌کند.

    سبک‌ها از پنل قابل تغییرند — هیچ‌چیز اینجا ثابت نیست.
    """
    n = clean_name(raw)
    if not n:
        return ""
    style = s("tkf_name_style", "plain")

    if style == "honor":
        suf = (s("tkf_name_suffix", "عزیز") or "").strip()
        return f"{n} {suf}".strip()

    if style == "title":
        pre = (s("tkf_name_prefix", "") or "").strip()
        return f"{pre} {n}".strip() if pre else n

    if style == "upper":
        # 🔠 حروف را با فاصله جدا کن — ظاهر رسمی و کشیده
        return "  ".join(w for w in n.split())

    return n


# ══════════════════════════════════════════════════════════
# 🖼️ موتور رسم
# ══════════════════════════════════════════════════════════
# ── 🧠 موتور چیدمان متن ──────────────────────────────────
# Pillow اگر با RAQM ساخته شده باشد، خودش حروف فارسی را
# می‌چسباند و راست‌به‌چپ می‌کند — بهترین کیفیت ممکن.
# اگر نبود، به arabic_reshaper برمی‌گردیم.
_RAQM = None


def _has_raqm():
    """
    🔍 آیا Pillow موتور RAQM دارد؟

    از همان منطق `certgen` استفاده می‌کند تا بلیط و گواهینامه
    هرگز دو رفتار متفاوت نداشته باشند — از جمله تنظیم دستی
    `fa_engine` (auto · raqm · basic).
    """
    global _RAQM
    try:
        import certgen
        return certgen._has_raqm()
    except Exception:
        pass
    if _RAQM is not None:
        return _RAQM
    try:
        from PIL import features
        _RAQM = bool(features.check("raqm"))
    except Exception:
        _RAQM = False
    return _RAQM


def _fa(t):
    """
    ✍️ آماده‌سازی متن فارسی برای رسم.

    🔴 نکتهٔ مهم: اگر RAQM هست، متن را **دست‌نخورده** برمی‌گردانیم
       چون خود Pillow شکل‌دهی می‌کند. دستکاری اضافه = متن برعکس.
    """
    t = str(t)
    if _has_raqm():
        return t
    try:
        import certgen
        return certgen._shape_fa(t)
    except Exception:
        return t


def _txt_kw():
    """🎯 پارامترهای رسم راست‌به‌چپ (فقط وقتی RAQM هست)"""
    if _has_raqm():
        return {"direction": "rtl", "language": "fa"}
    return {}


def _layout_engine():
    """
    ⚙️ موتور چیدمانی که فونت باید با آن ساخته شود.

    🔴 نکتهٔ حیاتی: موتور فونت باید با روش آماده‌سازی متن
       هماهنگ باشد، وگرنه متن **دو بار** برعکس می‌شود:

       RAQM  + متن خام            ✅ درست
       BASIC + متن معکوس‌شده      ✅ درست
       RAQM  + متن معکوس‌شده      ❌ برعکس!
       BASIC + متن خام            ❌ جدا و بی‌ترتیب
    """
    from PIL import ImageFont
    try:
        if _has_raqm():
            return ImageFont.Layout.RAQM
        return ImageFont.Layout.BASIC
    except Exception:
        return None


def _font(size, bold=False):
    """
    🔤 فونت فارسی.

    اولویت: تنظیم کاربر ← وزیرمتن ← فونت گواهینامه ← پیش‌فرض
    موتور چیدمان با روش آماده‌سازی متن هماهنگ می‌شود.
    """
    from PIL import ImageFont
    from pathlib import Path
    key = "tkf_font_bold" if bold else "tkf_font_path"
    cands = [s(key, "").strip(), s("tkf_font_path", "").strip()]
    try:
        from config import FILES_DIR
        fd = Path(FILES_DIR) / "fonts"
        if bold:
            cands += [str(fd / "Vazirmatn-Bold.ttf"),
                      str(fd / "Vazir-Bold.ttf")]
        cands += [str(fd / "Vazirmatn-Regular.ttf"),
                  str(fd / "Vazirmatn-Medium.ttf"),
                  str(fd / "Vazir.ttf")]
    except Exception:
        pass

    eng = _layout_engine()
    for c in cands:
        if c and Path(c).exists():
            try:
                return ImageFont.truetype(c, size, layout_engine=eng)
            except Exception:
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
    # 🩹 اگر وزیرمتن نبود، همان مسیر گواهینامه
    try:
        import certgen
        return certgen._find_font(size)
    except Exception:
        pass
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _tw(d, txt, font):
    """📏 پهنا و بلندای متن — با درنظرگرفتن جهت راست‌به‌چپ"""
    try:
        bb = d.textbbox((0, 0), txt, font=font, **_txt_kw())
        return bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        try:
            bb = d.textbbox((0, 0), txt, font=font)
            return bb[2] - bb[0], bb[3] - bb[1]
        except Exception:
            return len(txt) * 8, 14


def _draw_txt(d, xy, txt, font, fill, anchor=None):
    """🖌️ رسم متن با جهت درست — تنها راه مجاز نوشتن روی بلیط"""
    kw = dict(font=font, fill=fill)
    if anchor:
        kw["anchor"] = anchor
    try:
        d.text(xy, txt, **kw, **_txt_kw())
    except Exception:
        try:
            d.text(xy, txt, **kw)
        except Exception:
            pass


def build(data, out_path=None):
    """
    🎫 ساخت تصویر بلیط.

    data: dict با کلیدهای
        event · name · tracking · serial · form · date ·
        mobile · nid · amount · place · qr_data

    خروجی: مسیر فایل یا None
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log("⚠️ بلیط: Pillow نصب نیست")
        return None

    data = dict(data or {})
    W, H = size_wh()
    bg, band, band_txt, txt_col = palette()

    img = Image.new("RGB", (W, H), bg)

    # 🌄 تصویر پس‌زمینه
    bgp = asset_path("bg")
    if bgp:
        try:
            b = Image.open(bgp).convert("RGB")
            mode = s("tkf_bgimg_mode", "cover")
            if mode == "tile":
                for x in range(0, W, b.width):
                    for y in range(0, H, b.height):
                        img.paste(b, (x, y))
            elif mode == "fit":
                b2 = b.copy()
                b2.thumbnail((W, H))
                img.paste(b2, ((W - b2.width) // 2, (H - b2.height) // 2))
            else:  # cover
                r = max(W / b.width, H / b.height)
                b2 = b.resize((max(1, int(b.width * r)),
                               max(1, int(b.height * r))))
                img.paste(b2, ((W - b2.width) // 2, (H - b2.height) // 2))
        except Exception as e:
            log(f"⚠️ پس‌زمینه بلیط: {e}")

    d = ImageDraw.Draw(img)
    items = [b for b in layout() if b["on"]]

    # 🏷️ نوار عنوان
    band_h = 0
    has_header = any(b["key"] == "header" for b in items)
    if has_header:
        pct = max(5, min(40, s_num("tkf_band_h", 12)))
        band_h = int(H * pct / 100)
        d.rectangle([0, 0, W, band_h], fill=band)
        hb = next(b for b in items if b["key"] == "header")
        title = _fa(data.get("event") or data.get("form") or "بلیط")
        f = _font(hb["size"], bold=True)
        tw, th = _tw(d, title, f)
        _draw_txt(d, ((W - tw) / 2, (band_h - th) / 2 - 2), title,
                  f, band_txt)

    # 🖼️ کادر
    if s_on("tkf_border"):
        d.rectangle([8, band_h + 8, W - 8, H - 8], outline=band, width=3)

    # 🔵 گوشه تزئینی پایین
    if s_on("tkf_corner"):
        # 🔵 نوار پایین + برآمدگی نرم در گوشهٔ چپ
        #    (مثل نمونهٔ دیجی‌فرم — یک موج ملایم، نه ربع‌دایرهٔ شناور)
        base = max(6, int(H * 0.035))
        d.rectangle([0, H - base, W, H], fill=band)
        try:
            bw = int(W * 0.46)          # پهنای برآمدگی
            bh = int(H * 0.075)         # بلندی برآمدگی
            top_y = H - base - bh
            # مستطیل پایه از لبهٔ چپ
            d.rectangle([0, top_y, bw - bh, H - base], fill=band)
            # گوشهٔ گرد سمت راست برآمدگی
            d.pieslice([bw - bh * 2, top_y,
                        bw, top_y + bh * 2], 270, 360, fill=band)
        except Exception:
            pass

    # ═══ محتوا ═══
    #
    # 🎯 دو مرحله‌ای: اول همه چیز اندازه‌گیری می‌شود، بعد با
    #    فاصلهٔ درست چیده می‌شود. اینطور محتوا نه بالا جمع
    #    می‌شود نه از پایین بیرون می‌زند.
    body = [b for b in items if b["key"] != "header"]

    def value_of(k):
        if k == "name":
            return styled_name(data.get("name") or "")
        if k == "tracking":
            return data.get("tracking") or ""
        if k == "serial":
            return data.get("serial") or data.get("qr_data") or ""
        if k == "form":
            return data.get("form") or ""
        if k == "date":
            return data.get("date") or ""
        if k == "mobile":
            return data.get("mobile") or ""
        if k == "nid":
            return data.get("nid") or ""
        if k == "amount":
            return data.get("amount") or ""
        if k == "place":
            return data.get("place") or ""
        if k == "note":
            return s("tkf_note_text")
        if k == "footer":
            return s("tkf_footer_text")
        if k == "custom1":
            return s("tkf_custom1")
        if k == "custom2":
            return s("tkf_custom2")
        return ""

    qpct = max(10, min(70, s_num("tkf_qr_size", 30)))
    qsize = int(W * qpct / 100)
    qpad = max(6, int(qsize * 0.06)) if s_on("tkf_qr_frame") else 0

    # 📏 مرحله ۱ — اندازه‌گیری
    rows = []
    for b in body:
        k = b["key"]
        if k == "qr":
            if not data.get("qr_data"):
                continue
            rows.append({"kind": "qr", "h": qsize + qpad * 2})
            continue
        val = str(value_of(k)).strip()
        if not val:
            continue
        lbl = b.get("label") or ""
        line = f"{lbl} {val}".strip() if lbl else val
        f = _font(b.get("size") or 18)
        t = _fa(line)
        tw, th = _tw(d, t, f)
        rows.append({"kind": "text", "t": t, "f": f,
                     "w": tw, "h": max(th, 12)})

    if rows:
        # 🔵 فضای امن پایین (به‌خاطر کمان تزئینی)
        bottom_pad = int(H * 0.13) if s_on("tkf_corner") else int(H * 0.05)
        top = band_h + int(H * 0.05)
        avail = max(40, H - bottom_pad - top)
        content = sum(r["h"] for r in rows)

        gap_pct = max(0, min(20, s_num("tkf_gap", 3)))
        gap = int(H * gap_pct / 100)
        need = content + gap * max(0, len(rows) - 1)

        align = s("tkf_align", "spread")
        if align == "spread" and len(rows) > 1 and need < avail:
            # فاصله‌ها را پخش کن تا کل ارتفاع پر شود
            gap = int((avail - content) / (len(rows) - 1))
            gap = min(gap, int(H * 0.10))
            need = content + gap * (len(rows) - 1)
            y = top
        elif align == "center":
            y = top + max(0, int((avail - need) / 2))
        else:
            y = top

        # اگر بیش از حد بلند شد، فاصله را کم کن
        if need > avail and len(rows) > 1:
            gap = max(2, int((avail - content) / (len(rows) - 1)))
            y = top

        # 🖌️ مرحله ۲ — رسم
        for r in rows:
            if r["kind"] == "qr":
                x = int((W - qsize) / 2)
                try:
                    import qrcode
                    qi = qrcode.make(str(data["qr_data"])).convert("RGB")
                    qi = qi.resize((qsize, qsize))
                    if qpad:
                        d.rectangle([x - qpad, y - qpad,
                                     x + qsize + qpad, y + qsize + qpad],
                                    fill=(255, 255, 255))
                    img.paste(qi, (x, y + 0))
                except ImportError:
                    d.rectangle([x, y, x + qsize, y + qsize],
                                outline=band, width=3)
                except Exception as e:
                    log(f"⚠️ کیوآر بلیط: {e}")
                y += r["h"] + gap
                continue
            _draw_txt(d, ((W - r["w"]) / 2, y), r["t"], r["f"],
                      r.get("col") or txt_col)
            y += r["h"] + gap

    # 🏛️ لوگو
    lp = asset_path("logo")
    if lp:
        try:
            lo = Image.open(lp).convert("RGBA")
            pct = max(4, min(40, s_num("tkf_logo_size", 12)))
            lw = int(W * pct / 100)
            ratio = lw / max(1, lo.width)
            lo = lo.resize((lw, max(1, int(lo.height * ratio))))
            pad = max(4, s_num("tkf_logo_pad", 18))
            pos = s("tkf_logo_pos", "tr")
            xy = {
                "tl": (pad, pad),
                "tr": (W - lo.width - pad, pad),
                "bl": (pad, H - lo.height - pad),
                "br": (W - lo.width - pad, H - lo.height - pad),
                "tc": (int((W - lo.width) / 2), pad),
                "bc": (int((W - lo.width) / 2), H - lo.height - pad),
            }.get(pos, (W - lo.width - pad, pad))
            img.paste(lo, xy, lo)
        except Exception as e:
            log(f"⚠️ لوگوی بلیط: {e}")

    # 💾 ذخیره
    try:
        TICKET_DIR.mkdir(parents=True, exist_ok=True)
        if not out_path:
            tag = (data.get("tracking") or data.get("serial")
                   or str(int(time.time())))
            safe = "".join(ch for ch in str(tag)
                           if ch.isalnum() or ch in "-_")[:40]
            out_path = TICKET_DIR / f"tk_{safe}_{int(time.time()) % 10000}.jpg"
        img.save(str(out_path), "JPEG", quality=92)
        return str(out_path)
    except Exception as e:
        log(f"⚠️ ذخیره بلیط: {e}")
        return None


def build_for_response(rid):
    """
    🎫 ساخت بلیط از روی پاسخ فرم.

    🎯 «فقط برای فرم فعال باشه»
    """
    from forms import get_form, fmt_amount
    r = db_execute("SELECT * FROM form_responses WHERE id=?",
                   (int(rid),), fetch="one")
    if not r:
        return None
    form = get_form(r["form_id"])
    if not form:
        return None

    # 👤 نام — اولویت با پاسخ خودِ فرم، نه نام پروفایل بله
    #    چون نام بله معمولاً مستعار است («سوپرادمین»)
    mobile = nid = ""
    try:
        from auth import get_user
        u = get_user(r.get("bale_user_id")) or {}
        mobile = u.get("mobile") or ""
        nid = u.get("national_id") or ""
        profile_name = f"{u.get('first_name') or ''} " \
                       f"{u.get('last_name') or ''}".strip()
    except Exception:
        profile_name = ""

    name = ""
    try:
        import form_fill
        name = (form_fill._find_name_answer(rid) or "").strip()
    except Exception:
        pass
    if not name:
        name = profile_name
    name = clean_name(name)

    amount = ""
    if r.get("amount") and r.get("payment_status") == "paid":
        try:
            amount = f"{fmt_amount(r['amount'])}"
        except Exception:
            amount = str(r["amount"])

    date = ""
    try:
        from forms import jnow
        date = str(r.get("completed_at") or "")[:16] or jnow()
    except Exception:
        date = str(r.get("completed_at") or "")[:16]

    tracking = r.get("tracking_code") or ""
    serial = r.get("qr_code") or ""
    qr_data = serial or tracking

    return build({
        "event": form.get("title") or "",
        "form": form.get("title") or "",
        "name": name,
        "tracking": tracking,
        "serial": serial,
        "qr_data": qr_data,
        "date": date,
        "mobile": mobile,
        "nid": nid,
        "amount": amount,
        "place": form.get("location") or "",
    })


def build_shared_form_ticket(data, out_path=None):
    """Render the finalized image design for shared-server form tickets only."""
    from form_ticket_image import build_shared_form_ticket_image

    return build_shared_form_ticket_image(data, out_path=out_path)


def cleanup(force=False):
    """🧹 پاکسازی فایل‌های قدیمی بلیط"""
    hours = s_num("tkf_keep_hours", 48)
    if not force and hours <= 0:
        return 0, 0
    if not TICKET_DIR.exists():
        return 0, 0
    cut = time.time() - (hours * 3600)
    n = kb = 0
    for f in TICKET_DIR.glob("tk_*"):
        try:
            st = f.stat()
            if force or st.st_mtime < cut:
                kb += st.st_size // 1024
                f.unlink()
                n += 1
        except OSError:
            continue
    return n, kb


def stats():
    if not TICKET_DIR.exists():
        return {"count": 0, "kb": 0}
    n = kb = 0
    for f in TICKET_DIR.glob("tk_*"):
        try:
            n += 1
            kb += f.stat().st_size // 1024
        except OSError:
            continue
    return {"count": n, "kb": kb}


# ══════════════════════════════════════════════════════════
# 🖥️ پنل مدیریت بلیط
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    from bale_api import send
    from auth import is_admin
    if not is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.has_perm(uid, "sys_settings"):
        send(cid, "🔒 این بخش فقط برای سوپرادمین است")
        return False
    return True


def show_panel(cid, uid):
    """🎫 پنل اصلی بلیط فرم"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return

    on = [b for b in layout() if b["on"]]
    w, h = size_wh()
    pal = s("tkf_palette", "cream")
    pname = PALETTES.get(pal, ("—",))[0]
    fs = stats()

    lines = ["🎫 بلیط فرم", "━━━━━━━━━━━━━━", "",
             f"{'🟢 روشن' if enabled() else '🔴 خاموش'} — "
             f"بعد از تکمیل فرم فرستاده می‌شود", "",
             f"🧱 بلوک فعال: {len(on)} از {len(BLOCK_KEYS)}",
             f"📐 اندازه: {w}×{h}",
             f"🎨 رنگ‌بندی: {pname}",
             f"🏛️ لوگو: {'✅ دارد' if asset_path('logo') else '⚪ ندارد'}",
             f"🌄 پس‌زمینه: "
             f"{'✅ تصویر' if asset_path('bg') else '⚪ رنگ ساده'}",
             f"💾 فایل ذخیره‌شده: {fs['count']} ({fs['kb']} KB)", "",
             "━━━━━━━━━━━━━━", "چیدمان فعلی:", ""]
    for b in on[:8]:
        m = block_meta(b["key"])
        if m:
            lines.append(f"   {m[1]} {m[2]}")
    if len(on) > 8:
        lines.append(f"   … و {len(on) - 8} مورد دیگر")
    if not on:
        lines.append("   ⚠️ همه بلوک‌ها خاموش‌اند — بلیط خالی می‌شود!")

    btns = [
        [{"text": f"{'✅' if enabled() else '❌'} بلیط تصویری فرم",
          "callback_data": "tkb_tkf_on"}],
        [{"text": f"🧱 بلوک‌های بلیط ({len(on)})",
          "callback_data": "tk_blocks"}],
        [{"text": "🎨 ظاهر و رنگ", "callback_data": "tk_style"},
         {"text": "📐 اندازه", "callback_data": "tk_size"}],
        [{"text": "🏛️ لوگو و پس‌زمینه", "callback_data": "tk_assets"}],
        [{"text": "🔤 متن و فونت", "callback_data": "tk_text"}],
        [{"text": "⚙️ تنظیمات بیشتر", "callback_data": "tk_more"}],
        [{"text": "👁️ پیش‌نمایش زنده", "callback_data": "tk_prev"}],
    ]
    if fs["count"]:
        btns.append([{"text": f"🧹 پاکسازی ({fs['count']} فایل)",
                      "callback_data": "tk_clean"}])
    btns.append([{"text": "🔙 گواهینامه و بلیط",
                  "callback_data": "ct_hub"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_blocks(cid, uid):
    """
    🧱 مدیریت بلوک‌ها — کم و زیاد و جابه‌جا کردن.

    🎯 «اینو تو پنل مرتبط با بلیط قابل کم و زیاد و اضافه کردن باشه»
    """
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    items = layout()
    lines = ["🧱 بلوک‌های بلیط", "━━━━━━━━━━━━━━", "",
             "هر ردیف را روشن/خاموش کنید یا بالا و پایین ببرید:", ""]
    btns = []
    for i, b in enumerate(items):
        m = block_meta(b["key"])
        mark = "🟢" if b["on"] else "⚪"
        lines.append(f"{mark} {i + 1}. {m[1]} {m[2]}")
        row = [{"text": f"{mark} {m[1]} {m[2]}"[:26],
                "callback_data": f"tkbt_{b['key']}"}]
        if i > 0:
            row.append({"text": "🔼", "callback_data": f"tkup_{b['key']}"})
        if i < len(items) - 1:
            row.append({"text": "🔽", "callback_data": f"tkdn_{b['key']}"})
        row.append({"text": "⚙️", "callback_data": f"tkbe_{b['key']}"})
        btns.append(row)

    lines += ["", "🟢 = نمایش داده می‌شود   ⚪ = خاموش",
              "⚙️ = اندازه و برچسب"]
    btns.append([{"text": "♻️ بازگشت به چیدمان پیش‌فرض",
                  "callback_data": "tk_reset"}])
    btns.append([{"text": "👁️ پیش‌نمایش", "callback_data": "tk_prev"}])
    btns.append([{"text": "🔙 بلیط", "callback_data": "tk_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_block_edit(cid, uid, key):
    """⚙️ ویرایش یک بلوک — اندازه و برچسب"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    m = block_meta(key)
    b = block_of(key)
    if not m or not b:
        from bale_api import send
        return send(cid, "❌ نامعتبر")

    lines = [f"⚙️ {m[1]} {m[2]}", "━━━━━━━━━━━━━━", "",
             f"وضعیت: {'🟢 روشن' if b['on'] else '⚪ خاموش'}",
             f"🔠 اندازه متن: {b['size']}",
             f"🏷️ برچسب: {b.get('label') or '— بدون برچسب —'}"]
    if key == "qr":
        lines += ["", "💡 اندازهٔ کیوآر از «🎨 ظاهر» تنظیم می‌شود"]
    if key in ("note", "footer", "custom1", "custom2"):
        skey = {"note": "tkf_note_text", "footer": "tkf_footer_text",
                "custom1": "tkf_custom1", "custom2": "tkf_custom2"}[key]
        lines += ["", f"📝 متن: {s(skey) or '— خالی —'}"]

    btns = [[{"text": f"{'🟢 روشن' if b['on'] else '⚪ خاموش'} — تغییر",
              "callback_data": f"tkbt_{key}"}]]
    if key != "qr":
        btns.append([{"text": "🔠 کوچک‌تر",
                      "callback_data": f"tksz_{key}_-2"},
                     {"text": f"{b['size']}", "callback_data": "noop"},
                     {"text": "🔡 بزرگ‌تر",
                      "callback_data": f"tksz_{key}_2"}])
        btns.append([{"text": "🏷️ تغییر برچسب",
                      "callback_data": f"tklb_{key}"}])
    if key in ("note", "footer", "custom1", "custom2"):
        skey = {"note": "tkf_note_text", "footer": "tkf_footer_text",
                "custom1": "tkf_custom1", "custom2": "tkf_custom2"}[key]
        btns.append([{"text": "📝 تغییر متن",
                      "callback_data": f"tke_{skey}"}])
    btns.append([{"text": "👁️ پیش‌نمایش", "callback_data": "tk_prev"}])
    btns.append([{"text": "🔙 بلوک‌ها", "callback_data": "tk_blocks"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_style(cid, uid):
    """🎨 رنگ و ظاهر"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    cur = s("tkf_palette", "cream")
    lines = ["🎨 ظاهر بلیط", "━━━━━━━━━━━━━━", "", "رنگ‌بندی:", ""]
    for k, v in PALETTES.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {v[0]}")
    lines += ["", "━━━━━━━━━━━━━━",
              f"📏 ارتفاع نوار: {s_num('tkf_band_h', 12)}٪",
              f"🔳 اندازه کیوآر: {s_num('tkf_qr_size', 30)}٪",
              f"↕️ فاصله سطرها: {s_num('tkf_gap', 3)}٪",
              f"📐 چیدمان: {s('tkf_align', 'spread')}"]

    btns = [[{"text": f"{'🔘' if k == cur else '▫️'} {v[0]}",
              "callback_data": f"tkpal_{k}"}]
            for k, v in PALETTES.items()]
    if cur == "custom":
        btns.append([{"text": f"🎨 پس‌زمینه: {s('tkf_bg')}",
                      "callback_data": "tke_tkf_bg"}])
        btns.append([{"text": f"🎀 نوار: {s('tkf_band')}",
                      "callback_data": "tke_tkf_band"}])
        btns.append([{"text": f"🔤 متن نوار: {s('tkf_band_text')}",
                      "callback_data": "tke_tkf_band_text"}])
        btns.append([{"text": f"🖋️ متن اصلی: {s('tkf_text')}",
                      "callback_data": "tke_tkf_text"}])
    btns += [
        [{"text": f"📏 ارتفاع نوار: {s_num('tkf_band_h', 12)}٪",
          "callback_data": "tke_tkf_band_h"},
         {"text": f"🔳 کیوآر: {s_num('tkf_qr_size', 30)}٪",
          "callback_data": "tke_tkf_qr_size"}],
        [{"text": f"↕️ فاصله: {s_num('tkf_gap', 3)}٪",
          "callback_data": "tke_tkf_gap"},
         {"text": f"📐 چیدمان: {s('tkf_align', 'spread')}",
          "callback_data": "tk_align"}],
        [{"text": f"{'✅' if s_on('tkf_corner') else '❌'} گوشهٔ تزئینی",
          "callback_data": "tkb_tkf_corner"},
         {"text": f"{'✅' if s_on('tkf_border') else '❌'} کادر",
          "callback_data": "tkb_tkf_border"}],
        [{"text": f"{'✅' if s_on('tkf_qr_frame') else '❌'} قاب کیوآر",
          "callback_data": "tkb_tkf_qr_frame"}],
        [{"text": "👁️ پیش‌نمایش", "callback_data": "tk_prev"}],
        [{"text": "🔙 بلیط", "callback_data": "tk_panel"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_size(cid, uid):
    """📐 اندازه بلیط"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    cur = s("tkf_size", "portrait")
    w, h = size_wh()
    lines = ["📐 اندازه بلیط", "━━━━━━━━━━━━━━", "",
             f"📏 فعلی: {w}×{h} پیکسل", ""]
    for k, v in SIZES.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {v[0]}")

    btns = [[{"text": f"{'🔘' if k == cur else '▫️'} {v[0]}",
              "callback_data": f"tksize_{k}"}]
            for k, v in SIZES.items()]
    if cur == "custom":
        btns.append([{"text": f"↔️ پهنا: {s_num('tkf_w', 600)}",
                      "callback_data": "tke_tkf_w"},
                     {"text": f"↕️ بلندا: {s_num('tkf_h', 800)}",
                      "callback_data": "tke_tkf_h"}])
    btns.append([{"text": "👁️ پیش‌نمایش", "callback_data": "tk_prev"}])
    btns.append([{"text": "🔙 بلیط", "callback_data": "tk_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_assets(cid, uid):
    """
    🏛️ لوگو و پس‌زمینه.

    🎯 «لوگو ربات رو من میفرستم بعدا تو قسمت مدیریت بلیط،
       یه گوشه بلیط لوگو ربات باشه در هر بلیط»
    """
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    lg = asset_path("logo")
    bgp = asset_path("bg")
    pos = s("tkf_logo_pos", "tr")

    lines = ["🏛️ لوگو و پس‌زمینه", "━━━━━━━━━━━━━━", "",
             f"🏛️ لوگو: {'✅ ثبت شده' if lg else '⚪ ثبت نشده'}"]
    if lg:
        lines += [f"   📍 جای آن: {LOGO_POS.get(pos, pos)}",
                  f"   📐 اندازه: {s_num('tkf_logo_size', 12)}٪ پهنا",
                  f"   ↔️ فاصله از لبه: {s_num('tkf_logo_pad', 18)}px"]
    lines += ["", f"🌄 پس‌زمینه: "
                  f"{'✅ تصویر دارد' if bgp else '⚪ فقط رنگ'}"]
    if bgp:
        lines.append(f"   🖼️ حالت: {s('tkf_bgimg_mode', 'cover')}")
    lines += ["", "💡 لوگو ترجیحاً PNG با پس‌زمینه شفاف باشد.",
              "💡 پس‌زمینه به اندازهٔ بلیط بریده/کشیده می‌شود."]

    btns = [[{"text": "🏛️ آپلود لوگو" if not lg else "🔄 تعویض لوگو",
              "callback_data": "tka_logo"}]]
    if lg:
        btns.append([{"text": f"📍 جای لوگو: {LOGO_POS.get(pos, pos)}",
                      "callback_data": "tk_logopos"}])
        btns.append([{"text": f"📐 اندازه: {s_num('tkf_logo_size', 12)}٪",
                      "callback_data": "tke_tkf_logo_size"},
                     {"text": f"↔️ فاصله: {s_num('tkf_logo_pad', 18)}",
                      "callback_data": "tke_tkf_logo_pad"}])
        btns.append([{"text": "🗑️ حذف لوگو",
                      "callback_data": "tkd_logo"}])
    btns.append([{"text": "🌄 آپلود پس‌زمینه" if not bgp
                          else "🔄 تعویض پس‌زمینه",
                  "callback_data": "tka_bg"}])
    if bgp:
        btns.append([{"text": f"🖼️ حالت: {s('tkf_bgimg_mode', 'cover')}",
                      "callback_data": "tk_bgmode"}])
        btns.append([{"text": "🗑️ حذف پس‌زمینه",
                      "callback_data": "tkd_bg"}])
    btns.append([{"text": "👁️ پیش‌نمایش", "callback_data": "tk_prev"}])
    btns.append([{"text": "🔙 بلیط", "callback_data": "tk_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_text(cid, uid):
    """
    🔤 متن و فونت بلیط.

    اینجا سبک نوشتن نام و فونت فارسی تنظیم می‌شود.
    """
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return

    style = s("tkf_name_style", "plain")
    st_fa = dict((k, v) for k, v, _e in NAME_STYLES).get(style, style)
    sample = styled_name("علی رضایی")

    fp = (s("tkf_font_path", "") or "").strip()
    fb = (s("tkf_font_bold", "") or "").strip()
    raqm = _has_raqm()

    from database import get_setting as _gs
    eng = (_gs("fa_engine", "auto") or "auto").strip().lower()
    eng_fa = {"auto": "🤖 خودکار", "raqm": "🟢 RAQM",
              "basic": "🟡 ساده"}.get(eng, eng)

    lines = ["🔤 متن و فونت بلیط", "━━━━━━━━━━━━━━", "",
             f"👤 سبک نام: {st_fa}",
             f"   نمونه: «{sample}»", "",
             f"🔤 فونت متن: {'📁 دلخواه' if fp else '✅ وزیرمتن'}",
             f"🅱️ فونت عنوان: {'📁 دلخواه' if fb else '✅ وزیرمتن پررنگ'}", "",
             f"⚙️ موتور چیدمان: {eng_fa}",
             f"   الان فعال: {'RAQM' if raqm else 'ساده'}", ""]
    lines += ["━━━━━━━━━━━━━━",
              "💡 اگر حروف فارسی برعکس یا جدا افتادند،",
              "   موتور چیدمان را دستی عوض کنید.", "",
              "💡 نام‌هایی مثل «سوپرادمین» یا «کاربر» نام واقعی",
              "   حساب نمی‌شوند و به‌جایشان عبارت مهربان می‌آید."]

    btns = [
        [{"text": f"👤 سبک نام: {st_fa}", "callback_data": "tk_ns"}],
        [{"text": "💚 عبارت بعد از نام", "callback_data": "tke_tkf_name_suffix"},
         {"text": "🎗️ عنوان پیش از نام",
          "callback_data": "tke_tkf_name_prefix"}],
        [{"text": "🔤 مسیر فونت متن", "callback_data": "tke_tkf_font_path"}],
        [{"text": "🅱️ مسیر فونت عنوان", "callback_data": "tke_tkf_font_bold"}],
        [{"text": f"⚙️ موتور چیدمان: {eng_fa}",
          "callback_data": "tk_eng"}],
        [{"text": "🧪 تست چیدمان فارسی", "callback_data": "tk_fatest"}],
        [{"text": "👁️ پیش‌نمایش زنده", "callback_data": "tk_prev"}],
        [{"text": "🔙 پنل بلیط", "callback_data": "tk_panel"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_engine(cid, uid):
    """⚙️ انتخاب دستی موتور چیدمان فارسی"""
    from bale_api import send_or_edit
    from database import get_setting as _gs
    if not _guard(cid, uid):
        return
    cur = (_gs("fa_engine", "auto") or "auto").strip().lower()
    opts = {
        "auto": "🤖 خودکار — خودش تشخیص بدهد",
        "raqm": "🟢 RAQM — چیدمان پیشرفته",
        "basic": "🟡 ساده — سازگار با همه‌جا",
    }
    lines = ["⚙️ موتور چیدمان فارسی", "━━━━━━━━━━━━━━", "",
             "اگر حروف فارسی روی بلیط یا گواهینامه",
             "برعکس یا جدا از هم افتادند، این را عوض کنید.", "",
             "🤖 خودکار برای بیشتر سیستم‌ها درست است.",
             "   اگر نشد، «ساده» را امتحان کنید.", ""]
    for k, v in opts.items():
        lines.append(f"{'🔘' if k == cur else '▫️'} {v}")

    btns = [[{"text": f"{'🔘' if k == cur else '▫️'} {v}",
              "callback_data": f"tkeng_{k}"}] for k, v in opts.items()]
    btns.append([{"text": "🧪 تست چیدمان", "callback_data": "tk_fatest"}])
    btns.append([{"text": "🔙 متن و فونت", "callback_data": "tk_text"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_engine(cid, uid, val):
    """⚙️ ذخیرهٔ موتور چیدمان"""
    from bale_api import send
    if not _guard(cid, uid):
        return
    if val not in ("auto", "raqm", "basic"):
        return send(cid, "❌ نامعتبر")
    set_setting("fa_engine", val, "موتور چیدمان فارسی", "ticket", uid)
    # 🔄 کش تشخیص پاک شود تا فوری اثر کند
    try:
        import certgen
        certgen._RAQM_OK = None
        certgen._BIDI_MODE = None
    except Exception:
        pass
    global _RAQM
    _RAQM = None
    return show_engine(cid, uid)


def fa_test(cid, uid):
    """
    🧪 تست بصری چیدمان فارسی.

    یک تصویر می‌سازد که هر سه حالت را کنار هم نشان می‌دهد،
    تا کاربر با چشم خودش ببیند کدام درست است.
    """
    from bale_api import send, send_photo
    if not _guard(cid, uid):
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
        import certgen
    except Exception as e:
        return send(cid, f"❌ کتابخانه تصویر در دسترس نیست: {user_error_message(e)}")

    samples = ["سوپرادمین", "کمپ تابستانی کارآفرینی", "علی رضایی"]
    W, rowh = 1000, 78
    img = Image.new("RGB", (W, rowh * (len(samples) * 2 + 1) + 30),
                    (255, 255, 255))
    d = ImageDraw.Draw(img)
    big = _font(34)
    lbl = _font(15)

    _sv = (certgen._RAQM_OK, certgen._BIDI_MODE)
    y = 20
    d.text((W - 30, y), _fa("۱) موتور فعلی — باید درست باشد"),
           font=lbl, fill=(0, 120, 0), anchor="ra", **_txt_kw())
    y += 34
    for t in samples:
        _draw_txt(d, (W - 30, y), _fa(t), big, (0, 0, 0), anchor="ra")
        y += rowh
    y += 10
    d.text((W - 30, y), _fa("۲) حالت جایگزین — برای مقایسه"),
           font=lbl, fill=(180, 80, 0), anchor="ra", **_txt_kw())
    y += 34
    try:
        certgen._RAQM_OK = not certgen._has_raqm()
        certgen._BIDI_MODE = None
        for t in samples:
            _draw_txt(d, (W - 30, y), _fa(t), big, (0, 0, 0), anchor="ra")
            y += rowh
    finally:
        certgen._RAQM_OK, certgen._BIDI_MODE = _sv
        global _RAQM
        _RAQM = None

    try:
        from config import FILES_DIR
        from pathlib import Path
        outd = Path(FILES_DIR) / "tickets"
        outd.mkdir(parents=True, exist_ok=True)
        p = str(outd / "fa_test.jpg")
        img.convert("RGB").save(p, quality=92)
    except Exception as e:
        return send(cid, f"❌ ذخیره ناموفق: {user_error_message(e)}")

    cap = ("🧪 تست چیدمان فارسی\n\n"
           "بخش ۱ با موتور فعلی کشیده شده.\n"
           "بخش ۲ با حالت جایگزین.\n\n"
           "💡 هرکدام درست‌تر است، همان را در\n"
           "«⚙️ موتور چیدمان» انتخاب کنید.")
    r = send_photo(cid, p, cap)
    if not r.get("ok"):
        send(cid, "❌ ارسال تصویر ناموفق بود")
    return show_engine(cid, uid)


def show_more(cid, uid):
    """⚙️ تنظیمات بیشتر"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    lines = ["⚙️ تنظیمات بیشتر بلیط", "━━━━━━━━━━━━━━", "",
             f"📝 یادداشت: {s('tkf_note_text') or '—'}",
             f"🏛️ پانویس: {s('tkf_footer_text') or '—'}",
             f"✏️ متن دلخواه ۱: {s('tkf_custom1') or '—'}",
             f"✏️ متن دلخواه ۲: {s('tkf_custom2') or '—'}",
             f"⏰ نگهداری فایل: {s_num('tkf_keep_hours', 48)} ساعت", "",
             "💡 این متن‌ها وقتی دیده می‌شوند که بلوکشان",
             "   از «🧱 بلوک‌ها» روشن باشد."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📝 یادداشت", "callback_data": "tke_tkf_note_text"}],
        [{"text": "🏛️ پانویس", "callback_data": "tke_tkf_footer_text"}],
        [{"text": "✏️ متن دلخواه ۱", "callback_data": "tke_tkf_custom1"}],
        [{"text": "✏️ متن دلخواه ۲", "callback_data": "tke_tkf_custom2"}],
        [{"text": f"⏰ نگهداری: {s_num('tkf_keep_hours', 48)} ساعت",
          "callback_data": "tke_tkf_keep_hours"}],
        [{"text": "🧱 بلوک‌ها", "callback_data": "tk_blocks"}],
        [{"text": "🔙 بلیط", "callback_data": "tk_panel"}]]})


def show_pick(cid, uid, what):
    """🔀 انتخاب از فهرست (جای لوگو / حالت پس‌زمینه / چیدمان)"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    if what == "logopos":
        cur = s("tkf_logo_pos", "tr")
        opts = LOGO_POS
        title = "📍 جای لوگو روی بلیط"
    elif what == "bgmode":
        cur = s("tkf_bgimg_mode", "cover")
        opts = {"cover": "🔳 پر کردن کامل (برش می‌خورد)",
                "fit": "🔲 جا شدن کامل (حاشیه می‌ماند)",
                "tile": "🧱 تکرار کاشی‌وار"}
        title = "🖼️ حالت تصویر پس‌زمینه"
    elif what == "namestyle":
        cur = s("tkf_name_style", "plain")
        sample = clean_name("علی رضایی")
        suf = (s("tkf_name_suffix", "عزیز") or "").strip()
        pre = (s("tkf_name_prefix", "") or "").strip() or "جناب آقای"
        opts = {
            "plain": f"👤 ساده — «{sample}»",
            "honor": f"💚 با احترام — «{sample} {suf}»",
            "title": f"🎗️ با عنوان — «{pre} {sample}»",
            "upper": f"🔠 کشیده — «{'  '.join(sample.split())}»",
        }
        title = "👤 سبک نوشتن نام روی بلیط"
    else:
        cur = s("tkf_align", "spread")
        opts = {"spread": "↕️ پخش در کل بلیط",
                "center": "🎯 وسط‌چین",
                "top": "⬆️ از بالا"}
        title = "📐 چیدمان عمودی محتوا"

    lines = [title, "━━━━━━━━━━━━━━", ""]
    for k, v in opts.items():
        lines.append(f"{'🔘' if k == cur else '▫️'} {v}")

    # 🔎 صریح نوشته می‌شود تا ابزار بازبینی هم بتواند بررسی کند
    btns = []
    for k, v in opts.items():
        mark = "🔘" if k == cur else "▫️"
        if what == "logopos":
            cbd = f"tklp_{k}"
        elif what == "bgmode":
            cbd = f"tkbg_{k}"
        elif what == "namestyle":
            cbd = f"tkns_{k}"
        else:
            cbd = f"tkal_{k}"
        btns.append([{"text": f"{mark} {v}", "callback_data": cbd}])
    back = {"logopos": "tk_assets", "bgmode": "tk_assets",
            "namestyle": "tk_text"}.get(what, "tk_style")
    btns.append([{"text": "🔙 بازگشت", "callback_data": back}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def preview(cid, uid):
    """👁️ پیش‌نمایش زنده با داده نمونه"""
    from bale_api import send, send_photo, send_or_edit
    if not _guard(cid, uid):
        return
    send(cid, "🎨 در حال ساخت پیش‌نمایش...")
    try:
        from config import org_name
        org = org_name()
    except Exception:
        org = ""
    p = build({
        "event": "کمپ تابستانی کارآفرینی",
        "form": "کمپ تابستانی کارآفرینی",
        "name": "عرفان خدابنده‌لو",
        "tracking": "TL6032POXZ8840",
        "serial": "cbea38a331",
        "qr_data": "cbea38a331",
        "date": "1404/05/12",
        "mobile": "09121234567",
        "nid": "0010247165",
        "amount": "500,000 ریال",
        "place": org or "سالن اجتماعات",
    })
    if p and Path(p).exists():
        send_photo(cid, p, "👁️ پیش‌نمایش بلیط (داده نمونه)")
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
        txt = "✅ این همان چیزی است که کاربر می‌گیرد."
    else:
        txt = ("⚠️ ساخت پیش‌نمایش ناموفق بود.\n\n"
               "💡 مطمئن شوید Pillow نصب است:\n"
               "   py -m pip install Pillow qrcode")
    send_or_edit(cid, txt, {"inline_keyboard": [
        [{"text": "🔄 دوباره", "callback_data": "tk_prev"}],
        [{"text": "🧱 بلوک‌ها", "callback_data": "tk_blocks"},
         {"text": "🎨 ظاهر", "callback_data": "tk_style"}],
        [{"text": "🔙 بلیط", "callback_data": "tk_panel"}]]},
        force_new=True)


# ─────────── عملیات ───────────
def toggle_setting(cid, uid, key):
    from bale_api import send
    if not _guard(cid, uid):
        return
    r = _srow(key)
    if not r or r[3] != "bool":
        return send(cid, "❌ نامعتبر")
    set_setting(key, "0" if s(key) == "1" else "1", r[2], "ticket", uid)
    if key in ("tkf_corner", "tkf_border", "tkf_qr_frame"):
        return show_style(cid, uid)
    return show_panel(cid, uid)


def do_toggle_block(cid, uid, key):
    from bale_api import send
    if not _guard(cid, uid):
        return
    if key not in BLOCK_KEYS:
        return send(cid, "❌ نامعتبر")
    toggle_block(key, uid)
    return show_blocks(cid, uid)


def do_move(cid, uid, key, delta):
    if not _guard(cid, uid):
        return
    if key in BLOCK_KEYS:
        move_block(key, delta, uid)
    return show_blocks(cid, uid)


def do_size_step(cid, uid, key, delta):
    """🔠 بزرگ/کوچک کردن متن یک بلوک"""
    if not _guard(cid, uid):
        return
    b = block_of(key)
    if b:
        new = max(8, min(80, int(b["size"]) + int(delta)))
        set_block_field(key, "size", new, uid)
    return show_block_edit(cid, uid, key)


def do_reset(cid, uid):
    from bale_api import send
    if not _guard(cid, uid):
        return
    reset_layout(uid)
    send(cid, "♻️ چیدمان به حالت پیش‌فرض برگشت")
    return show_blocks(cid, uid)


def set_pick(cid, uid, what, val):
    from bale_api import send
    if not _guard(cid, uid):
        return
    mapping = {
        "pal": ("tkf_palette", PALETTES, show_style),
        "size": ("tkf_size", SIZES, show_size),
        "lp": ("tkf_logo_pos", LOGO_POS, show_assets),
        "bg": ("tkf_bgimg_mode", {"cover": 1, "fit": 1, "tile": 1},
               show_assets),
        "al": ("tkf_align", {"spread": 1, "center": 1, "top": 1},
               show_style),
        "ns": ("tkf_name_style",
               {"plain": 1, "honor": 1, "title": 1, "upper": 1},
               show_text),
    }
    row = mapping.get(what)
    if not row:
        return send(cid, "❌ نامعتبر")
    key, allowed, back = row
    if val not in allowed:
        return send(cid, "❌ نامعتبر")
    set_setting(key, val, key, "ticket", uid)
    # 🎨 پالت آماده → رنگ‌های دلخواه هم پر شوند تا قابل ویرایش باشند
    if what == "pal" and val != "custom":
        _n, bg, band, bt = PALETTES[val]
        set_setting("tkf_bg", bg, "رنگ پس‌زمینه", "ticket", uid)
        set_setting("tkf_band", band, "رنگ نوار", "ticket", uid)
        set_setting("tkf_band_text", bt, "رنگ متن نوار", "ticket", uid)
    return back(cid, uid)


def start_edit(cid, uid, key):
    """✏️ ورود مقدار متنی/عددی"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    r = _srow(key)
    if not r:
        return send(cid, "❌ نامعتبر")
    _, icon, name, kind, dflt, hint = r
    set_state(uid, STATE_TK_SET, {"key": key}, merge=False)
    txt = [f"✏️ {icon} {name}", "━━━━━━━━━━━━━━", "",
           f"📄 فعلی: {s(key) or '—'}", ""]
    if hint:
        txt += [f"💡 {hint}", ""]
    if kind == "num":
        txt.append("عدد بفرستید:")
    elif key in ("tkf_bg", "tkf_band", "tkf_band_text", "tkf_text"):
        txt += ["کد رنگ را بفرستید — مثال: #2E8B67", "",
                "💡 رنگ دلخواهتان را از سایت رنگ بگیرید."]
    else:
        txt.append("متن جدید را بنویسید:")
    txt.append("💡 برای بازگشت به پیش‌فرض، «-» بفرستید")
    send(cid, "\n".join(txt), kb_cancel())


def start_label(cid, uid, key):
    """🏷️ تغییر برچسب یک بلوک"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    m = block_meta(key)
    b = block_of(key)
    if not m or not b:
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_TK_SET, {"label_key": key}, merge=False)
    send(cid, (
        f"🏷️ برچسب {m[1]} {m[2]}\n━━━━━━━━━━━━━━\n\n"
        f"📄 فعلی: {b.get('label') or '— بدون برچسب —'}\n\n"
        f"متنی که قبل از مقدار می‌آید را بنویسید.\n"
        f"مثال: «کد پیگیری:»\n\n"
        f"💡 برای حذف برچسب، «-» بفرستید"
    ), kb_cancel())


def handle_edit(message):
    """📥 دریافت مقدار"""
    from bale_api import send, kb_remove, kb_cancel, BTN_BACK
    from auth import get_state_data, clear_state, normalize_digits
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid) or {}
    key = d.get("key")
    lkey = d.get("label_key")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        if lkey:
            return show_block_edit(cid, uid, lkey)
        return show_panel(cid, uid)

    # 🏷️ برچسب بلوک
    if lkey:
        set_block_field(lkey, "label", "" if raw == "-" else raw[:40], uid)
        clear_state(uid)
        send(cid, "✅ ذخیره شد", kb_remove())
        return show_block_edit(cid, uid, lkey)

    r = _srow(key)
    if not r:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "-":
        val = r[4]
    elif r[3] == "num":
        dg = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not dg:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        val = str(int(dg))
    else:
        val = raw[:200]
        if key in ("tkf_bg", "tkf_band", "tkf_band_text", "tkf_text"):
            v = val.strip().lstrip("#")
            if len(v) in (3, 6) and all(
                    c in "0123456789abcdefABCDEF" for c in v):
                val = "#" + v
            else:
                return send(cid, "⚠️ کد رنگ درست نیست.\n\n"
                                 "مثال: #2E8B67", kb_cancel())
            # رنگ دستی → پالت دلخواه شود
            set_setting("tkf_palette", "custom", "رنگ‌بندی",
                        "ticket", uid)

    set_setting(key, val, r[2], "ticket", uid)
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {val}", kb_remove())

    if key in ("tkf_w", "tkf_h"):
        return show_size(cid, uid)
    if key in ("tkf_logo_size", "tkf_logo_pad"):
        return show_assets(cid, uid)
    if key in ("tkf_bg", "tkf_band", "tkf_band_text", "tkf_text",
               "tkf_band_h", "tkf_qr_size", "tkf_gap"):
        return show_style(cid, uid)
    if key in ("tkf_note_text", "tkf_footer_text", "tkf_custom1",
               "tkf_custom2", "tkf_keep_hours"):
        return show_more(cid, uid)
    return show_panel(cid, uid)


def start_asset(cid, uid, kind):
    """📤 آپلود لوگو یا پس‌زمینه"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    if kind not in ("logo", "bg"):
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_TK_ASSET, {"kind": kind}, merge=False)
    if kind == "logo":
        send(cid, (
            "🏛️ لوگوی بلیط\n━━━━━━━━━━━━━━\n\n"
            "تصویر لوگو را بفرستید.\n\n"
            "💡 ترجیحاً PNG با پس‌زمینهٔ شفاف\n"
            "💡 برای شفافیت، به‌صورت «فایل» بفرستید نه «عکس»\n\n"
            "این لوگو روی همهٔ بلیط‌ها می‌نشیند."
        ), kb_cancel())
    else:
        w, h = size_wh()
        send(cid, (
            f"🌄 پس‌زمینهٔ بلیط\n━━━━━━━━━━━━━━\n\n"
            f"تصویر پس‌زمینه را بفرستید.\n\n"
            f"📐 اندازهٔ فعلی بلیط: {w}×{h}\n"
            f"💡 تصویری با همین نسبت بفرستید تا برش نخورد\n"
            f"💡 برای کیفیت بهتر، «فایل» بفرستید"
        ), kb_cancel())


def handle_asset(message):
    """📥 دریافت تصویر لوگو/پس‌زمینه"""
    from bale_api import (send, kb_remove, kb_cancel, BTN_BACK,
                          get_file_info, download_file)
    from auth import get_state_data, clear_state, log_action
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid) or {}
    kind = d.get("kind")

    txt = (message.get("text") or "").strip()
    if txt in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_assets(cid, uid)
    if kind not in ("logo", "bg"):
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    doc = message.get("document")
    photo = message.get("photo")
    if not doc and not photo:
        return send(cid, "⚠️ لطفاً تصویر را بفرستید:", kb_cancel())

    if doc:
        fid = doc.get("file_id")
        fname = str(doc.get("file_name") or "img.png").lower()
        if not fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return send(cid, "⚠️ فقط تصویر PNG یا JPG:", kb_cancel())
        ext = ".png" if fname.endswith(".png") else ".jpg"
    else:
        best = sorted(photo, key=lambda x: x.get("file_size") or 0)[-1]
        fid = best.get("file_id")
        ext = ".jpg"
        if kind == "logo":
            send(cid, "💡 نکته: برای پس‌زمینهٔ شفاف، PNG را "
                      "به‌صورت «فایل» بفرستید.")

    info = get_file_info(fid)
    if not info.get("ok"):
        return send(cid, "❌ دریافت فایل ناموفق")
    fpath = (info.get("result") or {}).get("file_path")
    data = download_file(fpath) if fpath else None
    if not data:
        return send(cid, "❌ دانلود ناموفق")

    import uuid as _uu
    TICKET_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    dest = TICKET_ASSET_DIR / f"{kind}_{int(time.time())}_" \
                              f"{_uu.uuid4().hex[:6]}{ext}"
    try:
        dest.write_bytes(data)
    except Exception as e:
        return send(cid, f"❌ ذخیره ناموفق: {user_error_message(e)}")

    # قبلی را پاک کن
    old = asset_path(kind)
    if old and Path(old) != dest:
        try:
            Path(old).unlink(missing_ok=True)
        except OSError:
            pass

    set_asset(kind, dest, uid)
    clear_state(uid)
    log_action(uid, "ticket_asset", {"kind": kind})
    send(cid, f"✅ {'لوگو' if kind == 'logo' else 'پس‌زمینه'} ذخیره شد 💚",
         kb_remove())
    return show_assets(cid, uid)


def remove_asset(cid, uid, kind):
    from bale_api import send
    if not _guard(cid, uid):
        return
    if kind not in ("logo", "bg"):
        return send(cid, "❌ نامعتبر")
    del_asset(kind, uid)
    send(cid, "🗑️ حذف شد")
    return show_assets(cid, uid)


def clean_now(cid, uid):
    from bale_api import send
    if not _guard(cid, uid):
        return
    n, kb = cleanup(force=True)
    send(cid, f"🧹 {n} فایل بلیط پاک شد ({kb} کیلوبایت)")
    return show_panel(cid, uid)
