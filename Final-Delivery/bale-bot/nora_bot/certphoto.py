# -*- coding: utf-8 -*-
"""
📷 عکس پرسنلی گواهینامه

🎯 گزارش شما:
   «من به بعضی گواهینامه ها پارامتر تصویر پرسنلی اضافه میکنم این
    برای هرکسی که پروفایلش عکس دار بود و عکسش تایید شده بود عکس
    پروفایلش تو اون قسمت قرار بگیره و اگه پنل عکس نداشت و گواهی
    جای عکس داشت یه تصویر آدمک ساده میزاری بدون هیچی ساده ساده»

منطق:
   ۱) کاربر عکس پروفایل دارد **و** پروفایلش تأیید شده  → همان عکس
   ۲) در غیر این صورت                                  → آدمک ساده

آدمک یک بار ساخته و کش می‌شود؛ خاکستری ملایم، بدون جزئیات.
"""
from pathlib import Path

from database import db_execute, get_setting, log

PHOTO_DIR = Path("files/certificates/photos")
SILHOUETTE = PHOTO_DIR / "silhouette.png"

# 🎨 رنگ‌های آدمک — از پنل قابل تغییر
DEF_BG = "#EEF1F4"          # پس‌زمینه
DEF_FG = "#B8C2CC"          # خود آدمک


def _hex(c, dflt):
    """«#EEF1F4» → (238, 241, 244)"""
    s = str(c or "").strip().lstrip("#")
    if len(s) != 6:
        s = dflt.lstrip("#")
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        d = dflt.lstrip("#")
        return tuple(int(d[i:i + 2], 16) for i in (0, 2, 4))


def make_silhouette(size=600, force=False):
    """
    🧍 آدمک ساده می‌سازد — دایرهٔ سر + نیم‌بیضی شانه.

    «ساده ساده» یعنی هیچ چهره، خط یا جزئیاتی ندارد.
    """
    if SILHOUETTE.exists() and not force:
        return str(SILHOUETTE)
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log("⚠️ Pillow نصب نیست — آدمک ساخته نشد")
        return None

    bg = _hex(get_setting("cert_photo_bg", DEF_BG), DEF_BG)
    fg = _hex(get_setting("cert_photo_fg", DEF_FG), DEF_FG)

    # ✳️ ۴ برابر می‌کشیم و کوچک می‌کنیم تا لبه‌ها نرم شود
    s = size * 4
    img = Image.new("RGB", (s, s), bg)
    d = ImageDraw.Draw(img)

    # 🔵 سر — دایره در بالای مرکز
    head_r = int(s * 0.155)
    head_cx = s // 2
    head_cy = int(s * 0.345)
    d.ellipse([head_cx - head_r, head_cy - head_r,
               head_cx + head_r, head_cy + head_r], fill=fg)

    # 👔 شانه — نیم‌بیضی که از پایین کادر بیرون می‌زند
    sh_w = int(s * 0.62)
    sh_top = int(s * 0.60)
    sh_h = int(s * 0.60)
    d.ellipse([head_cx - sh_w // 2, sh_top,
               head_cx + sh_w // 2, sh_top + sh_h], fill=fg)

    img = img.resize((size, size), Image.LANCZOS)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    img.save(str(SILHOUETTE))
    log(f"🧍 آدمک پیش‌فرض ساخته شد ({size}×{size})")
    return str(SILHOUETTE)


def photo_approved(user):
    """
    ✅ آیا عکس این کاربر قابل استفاده است؟

    دو شرط با هم:
      • فایل عکس روی دیسک باشد
      • پروفایل تأیید شده باشد

    از پنل می‌شود شرط تأیید را برداشت
    (`cert_photo_need_approve = 0`).
    """
    if not user:
        return False
    fp = user.get("profile_photo")
    if not fp or not Path(fp).exists():
        return False
    if get_setting("cert_photo_need_approve", "1") != "1":
        return True
    st = str(user.get("profile_status") or "").lower()
    return st == "approved" or bool(user.get("basic_profile_approved"))


def photo_for(bale_uid, user=None):
    """
    📷 مسیر عکسی که باید روی گواهینامه بنشیند.

    خروجی همیشه یک مسیر معتبر است (عکس واقعی یا آدمک) — مگر
    اینکه Pillow نصب نباشد.
    """
    if user is None and bale_uid:
        user = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                          (bale_uid,), fetch="one")
    if photo_approved(user):
        return user.get("profile_photo")
    if get_setting("cert_photo_fallback", "1") != "1":
        return None
    return make_silhouette()


def photo_state(bale_uid, user=None):
    """
    🔎 وضعیت عکس — برای نمایش در پنل ادمین.

    خروجی: (مسیر، برچسب فارسی، آیا واقعی است)
    """
    if user is None and bale_uid:
        user = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                          (bale_uid,), fetch="one")
    if not user:
        return None, "کاربر یافت نشد", False
    fp = user.get("profile_photo")
    if not fp:
        return photo_for(bale_uid, user), "عکس ندارد → آدمک", False
    if not Path(fp).exists():
        return photo_for(bale_uid, user), "فایل عکس گم شده → آدمک", False
    if not photo_approved(user):
        return (photo_for(bale_uid, user),
                "عکس تأیید نشده → آدمک", False)
    return fp, "عکس تأییدشده", True


def stats(uids=None):
    """
    📊 چند نفر عکس تأییدشده دارند؟

    uids=None یعنی کل کاربران.
    """
    out = {"total": 0, "real": 0, "fallback": 0}
    if uids is None:
        rows = db_execute("SELECT * FROM users", fetch="all") or []
    else:
        rows = []
        for u in uids:
            r = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                           (u,), fetch="one")
            if r:
                rows.append(r)
    for r in rows:
        out["total"] += 1
        if photo_approved(r):
            out["real"] += 1
        else:
            out["fallback"] += 1
    return out


# 🎛️ تنظیمات — همه از پنل قابل تغییر
PHOTO_SETTINGS = [
    ("cert_photo_need_approve", "✅", "فقط عکس تأییدشده", "bool", "1",
     "اگر خاموش باشد، هر عکس پروفایلی استفاده می‌شود"),
    ("cert_photo_fallback", "🧍", "آدمک برای بی‌عکس‌ها", "bool", "1",
     "اگر خاموش باشد، جای عکس خالی می‌ماند"),
    ("cert_photo_bg", "🎨", "رنگ پس‌زمینهٔ آدمک", "text", DEF_BG,
     "کد رنگ شش‌رقمی · مثال: #EEF1F4"),
    ("cert_photo_fg", "🖌️", "رنگ خود آدمک", "text", DEF_FG,
     "کد رنگ شش‌رقمی · مثال: #B8C2CC"),
]


def attach(mapping, bale_uid, tpl=None, enabled=True):
    """
    📎 عکس پرسنلی را به نقشهٔ پارامترها می‌چسباند.

    🎯 «من به بعضی گواهینامه‌ها پارامتر تصویر پرسنلی اضافه می‌کنم»

    این تابع **نقطهٔ واحد** همهٔ مسیرهای صدور است تا رفتار
    یکسان باشد:
        • مرکز صدور   (certcenter.build_one)
        • رویداد      (certissue.issue_one)
        • چندگواهینامه (eventcert.issue)
        • لینک اکسل   (certbatch.handle_claim)

    🔑 موتور `certgen.generate` عکس شخص را از کلید ویژهٔ
       `_photo` می‌خواند.

    اگر قالب پارامتر {عکس} نداشته باشد، هیچ کاری نمی‌کند —
    پس صدا زدنش همیشه بی‌خطر است.
    """
    if not enabled or mapping is None:
        return mapping
    try:
        # 📄 قالب اصلاً جای عکس دارد؟
        if tpl is not None:
            import json as _j
            import certgen as _cg
            keys = []
            try:
                keys = list(_j.loads(tpl.get("placeholders") or "[]"))
            except Exception:
                keys = []
            if keys and "photo" not in keys:
                return mapping
        if get_setting("cc_auto_photo", "1") != "1":
            return mapping
        p = photo_for(bale_uid)
        if p:
            mapping["_photo"] = str(p)
    except Exception as e:
        log(f"⚠️ چسباندن عکس پرسنلی: {e}")
    return mapping
