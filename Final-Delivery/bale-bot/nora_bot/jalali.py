# -*- coding: utf-8 -*-
"""
📅 تاریخ شمسی — یک منبع واحد برای کل ربات

🎯 گزارش شما:
   «چرا اطلاعات و تاریخ و چیزایی که برای کاربر ارسال میشه شمسی
    نیست؟ مثلا گواهینامه شما صادر شد برای کاربر رفته تاریخ ها
    خارجیه»

🔴 ریشهٔ مشکل:
   SQLite ستون‌های `issued_at` و `created_at` را با
   `CURRENT_TIMESTAMP` پر می‌کند → «2026-07-29 14:32:11».
   کد جاهای زیادی همین رشته را **خام** به کاربر نشان می‌داد:

       f"📅 {(cert.get('issued_at') or '')[:10]}"   ← 2026-07-29

   الگوریتم تبدیل شمسی وجود داشت ولی داخل `forms.py` دفن بود و
   سه نسخهٔ ناهماهنگ `today_jalali()` در ماژول‌های مختلف تکرار
   شده بود.

✅ این ماژول تنها مرجع تاریخ است. هیچ وابستگی بیرونی ندارد
   (jdatetime لازم نیست) و همه‌جا قابل import است.
"""
import re
from datetime import datetime, date, timedelta

# ─────────── نام‌ها ───────────
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
          "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

WEEKDAYS = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه",
            "چهارشنبه", "پنج‌شنبه", "جمعه"]

_FA = "۰۱۲۳۴۵۶۷۸۹"
_EN = "0123456789"
_AR = "٠١٢٣٤٥٦٧٨٩"


# ══════════════════════════════════════════════════════════
# 🔢 ارقام
# ══════════════════════════════════════════════════════════
def fa(text):
    """ارقام لاتین → فارسی"""
    s = str(text if text is not None else "")
    for i, d in enumerate(_EN):
        s = s.replace(d, _FA[i])
    return s


def en(text):
    """ارقام فارسی/عربی → لاتین"""
    s = str(text if text is not None else "")
    for i, d in enumerate(_FA):
        s = s.replace(d, _EN[i])
    for i, d in enumerate(_AR):
        s = s.replace(d, _EN[i])
    return s


# ══════════════════════════════════════════════════════════
# 🔄 تبدیل تقویم
# ══════════════════════════════════════════════════════════
def g2j(gy, gm, gd):
    """میلادی → شمسی · خروجی (سال، ماه، روز)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day_no = (365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100
                + (gy2 + 399) // 400 + g_d_m[gm2] + gd2)
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def j2g(jy, jm, jd):
    """شمسی → میلادی · خروجی (سال، ماه، روز)"""
    jy2 = jy - 979
    jm2 = jm - 1
    jd2 = jd - 1
    j_day_no = (365 * jy2 + (jy2 // 33) * 8 + (jy2 % 33 + 3) // 4)
    j_day_no += jm2 * 31 if jm2 < 7 else jm2 * 30 + 6
    j_day_no += jd2
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False
    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365
    sal_a = [0, 31,
             29 if leap else 28,
             31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and g_day_no >= sal_a[gm]:
        g_day_no -= sal_a[gm]
        gm += 1
    return gy, gm, g_day_no + 1


def is_leap(jy):
    """سال کبیسهٔ شمسی؟"""
    return ((jy + 12) % 33) % 4 == 1


def month_days(jy, jm):
    """تعداد روزهای یک ماه شمسی"""
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_leap(jy) else 29


# ══════════════════════════════════════════════════════════
# 📅 امروز
# ══════════════════════════════════════════════════════════
def today():
    """(سال، ماه، روز) شمسی امروز"""
    g = datetime.now()
    return g2j(g.year, g.month, g.day)


def today_str():
    """«۱۴۰۵/۰۵/۰۷» — با ارقام فارسی"""
    return fa("{:04d}/{:02d}/{:02d}".format(*today()))


def today_iso():
    """«1405/05/07» — ارقام لاتین، برای ذخیره در دیتابیس"""
    return "{:04d}/{:02d}/{:02d}".format(*today())


def weekday_name(gdt=None):
    """نام روز هفته"""
    g = gdt or datetime.now()
    # دوشنبهٔ پایتون = ۰ · شنبهٔ ما = ۰
    return WEEKDAYS[(g.weekday() + 2) % 7]


# ══════════════════════════════════════════════════════════
# 🧩 تجزیه و قالب‌بندی — قلب رفع باگ
# ══════════════════════════════════════════════════════════
_TS_RE = re.compile(
    r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?")


def parse(value):
    """
    🧠 هر چیزی را می‌گیرد و (jy, jm, jd, hh, mi) برمی‌گرداند.

    پشتیبانی می‌کند از:
      • «2026-07-29 14:32:11»   ← CURRENT_TIMESTAMP اسکیوالایت
      • «2026/07/29»
      • «1405/05/07»            ← از قبل شمسی، دست نمی‌خورد
      • datetime / date
      • ارقام فارسی

    🔑 تشخیص میلادی از شمسی: سالِ ≥ ۱۹۰۰ میلادی است.
       (سال شمسی هرگز به ۱۹۰۰ نمی‌رسد و میلادی هرگز زیر آن
        نمی‌آید — پس مرز امن است.)
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        jy, jm, jd = g2j(value.year, value.month, value.day)
        return jy, jm, jd, value.hour, value.minute
    if isinstance(value, date):
        jy, jm, jd = g2j(value.year, value.month, value.day)
        return jy, jm, jd, 0, 0

    m = _TS_RE.search(en(str(value)))
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4) or 0)
    mi = int(m.group(5) or 0)

    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None

    if y >= 1900:                      # میلادی → تبدیل کن
        try:
            jy, jm, jd = g2j(y, mo, d)
        except Exception:
            return None
        return jy, jm, jd, hh, mi
    return y, mo, d, hh, mi            # از قبل شمسی


def fmt(value, style="date", digits=True):
    """
    📅 هر تاریخی → رشتهٔ شمسی خوانا.

    style:
      date      ۱۴۰۵/۰۵/۰۷
      datetime  ۱۴۰۵/۰۵/۰۷ ۱۴:۳۲
      long      ۷ مرداد ۱۴۰۵
      longtime  ۷ مرداد ۱۴۰۵ — ساعت ۱۴:۳۲
      short     ۰۵/۰۷
      iso       1405/05/07   (ارقام لاتین — برای ذخیره)

    اگر ورودی خالی یا نامفهوم بود، «—» برمی‌گرداند تا هرگز
    تاریخ میلادی خام به کاربر نشان داده نشود.
    """
    p = parse(value)
    if not p:
        return "—"
    jy, jm, jd, hh, mi = p

    if style == "iso":
        return f"{jy:04d}/{jm:02d}/{jd:02d}"
    if style == "long":
        out = f"{jd} {MONTHS[jm - 1]} {jy}"
    elif style == "longtime":
        out = f"{jd} {MONTHS[jm - 1]} {jy} — ساعت {hh:02d}:{mi:02d}"
    elif style == "datetime":
        out = f"{jy:04d}/{jm:02d}/{jd:02d} {hh:02d}:{mi:02d}"
    elif style == "short":
        out = f"{jm:02d}/{jd:02d}"
    else:
        out = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return fa(out) if digits else out


def d(value):
    """میان‌بر: تاریخ کوتاه شمسی"""
    return fmt(value, "date")


def dt(value):
    """میان‌بر: تاریخ و ساعت شمسی"""
    return fmt(value, "datetime")


def long(value):
    """میان‌بر: «۷ مرداد ۱۴۰۵»"""
    return fmt(value, "long")


# ══════════════════════════════════════════════════════════
# ➕ محاسبات
# ══════════════════════════════════════════════════════════
def add_days(jdate, days):
    """چند روز به تاریخ شمسی اضافه کن · خروجی «1405/05/07»"""
    p = parse(jdate)
    if not p:
        return ""
    jy, jm, jd = p[0], p[1], p[2]
    try:
        gy, gm, gd = j2g(jy, jm, jd)
        g = date(gy, gm, gd) + timedelta(days=int(days))
        ny, nm, nd = g2j(g.year, g.month, g.day)
        return f"{ny:04d}/{nm:02d}/{nd:02d}"
    except Exception:
        return ""


def add_months(jdate, months):
    """
    چند ماه به تاریخ شمسی اضافه کن.

    اگر روز در ماه مقصد وجود نداشته باشد (۳۱ اسفند)، به آخرین
    روز همان ماه می‌چسبد.
    """
    p = parse(jdate)
    if not p:
        return ""
    jy, jm, jd = p[0], p[1], p[2]
    total = (jy * 12 + (jm - 1)) + int(months)
    ny, nm = total // 12, total % 12 + 1
    nd = min(jd, month_days(ny, nm))
    return f"{ny:04d}/{nm:02d}/{nd:02d}"


def to_num(jdate):
    """تاریخ شمسی → عدد مقایسه‌پذیر (۱۴۰۵۰۵۰۷)"""
    p = parse(jdate)
    if not p:
        return 0
    return p[0] * 10000 + p[1] * 100 + p[2]


def diff_days(a, b):
    """اختلاف دو تاریخ شمسی به روز (a − b)"""
    pa, pb = parse(a), parse(b)
    if not pa or not pb:
        return 0
    try:
        ga = date(*j2g(pa[0], pa[1], pa[2]))
        gb = date(*j2g(pb[0], pb[1], pb[2]))
        return (ga - gb).days
    except Exception:
        return 0


def days_left(jdate):
    """چند روز تا این تاریخ مانده؟ (منفی = گذشته)"""
    return diff_days(jdate, today_iso())


def ago(value):
    """
    ⏱️ «۳ روز پیش» · «۲ ساعت پیش» · «همین حالا»

    برای نمایش دوستانه در فهرست‌ها.
    """
    p = parse(value)
    if not p:
        return "—"
    try:
        gy, gm, gd = j2g(p[0], p[1], p[2])
        then = datetime(gy, gm, gd, p[3], p[4])
    except Exception:
        return fmt(value)
    sec = (datetime.now() - then).total_seconds()
    if sec < 0:
        return fmt(value, "datetime")
    if sec < 60:
        return "همین حالا"
    if sec < 3600:
        return f"{fa(int(sec // 60))} دقیقه پیش"
    if sec < 86400:
        return f"{fa(int(sec // 3600))} ساعت پیش"
    days = int(sec // 86400)
    if days < 31:
        return f"{fa(days)} روز پیش"
    if days < 366:
        return f"{fa(days // 30)} ماه پیش"
    return f"{fa(days // 365)} سال پیش"


def valid(jdate):
    """آیا رشتهٔ داده‌شده تاریخ شمسی معتبری است؟"""
    p = parse(jdate)
    if not p:
        return False
    jy, jm, jd = p[0], p[1], p[2]
    if not (1300 <= jy <= 1500):
        return False
    if not (1 <= jm <= 12):
        return False
    return 1 <= jd <= month_days(jy, jm)
