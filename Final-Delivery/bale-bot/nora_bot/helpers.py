# -*- coding: utf-8 -*-
"""
🧰 ابزارهای مشترک — فاز ۴۰

🎯 «سعی کن تا جای ممکن ربات لایت و روان بشه و جاهایی که راه
    داره چیزها ساده‌تر بشن»

🔴 چه چیزی تکرار شده بود؟
   اسکن نشان داد **۲۳ ماژول** هرکدام `_guard` جدا داشتند و
   **۵ ماژول** تابع `_fa` یکسان — در مجموع ۱۴۷ خط کد کاملاً
   تکراری.

⚠️ نکتهٔ مهم: نسخه‌های `_guard` **یکسان نبودند**؛ بعضی فقط
   ادمین را می‌سنجیدند و بعضی دسترسی بخش را هم. این ماژول
   فقط نسخهٔ **سادهٔ** مشترک را ارائه می‌دهد و ماژول‌هایی که
   منطق خاص دارند دست‌نخورده می‌مانند.
"""


def guard_admin(cid, uid, msg="❌ دسترسی ندارید"):
    """
    🛡️ بررسی سادهٔ ادمین‌بودن.

    اگر ادمین نبود پیام می‌دهد و False برمی‌گرداند.
    """
    from auth import is_admin
    from bale_api import send
    if not is_admin(uid):
        send(cid, msg)
        return False
    return True


def guard_section(cid, uid, section, msg=None):
    """
    🛡️ بررسی ادمین + دسترسی به یک بخش.

    برای ماژول‌هایی که علاوه بر ادمین‌بودن، مجوز بخش هم
    می‌خواهند (مثل ads → notify).
    """
    from auth import is_admin
    from bale_api import send
    if not is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    try:
        import permissions as perm
        if not perm.can_section(uid, section):
            send(cid, msg or f"🔒 دسترسی به «{section}» ندارید")
            return False
    except ImportError:
        pass
    return True


def fa(n):
    """🔢 ارقام لاتین → فارسی"""
    import jalali
    return jalali.fa(n)


def en(s):
    """🔢 ارقام فارسی/عربی → لاتین"""
    import jalali
    return jalali.en(s)


def short(txt, n=28, tail="…"):
    """
    ✂️ کوتاه‌کردن متن برای دکمه.

    بله سقف حدود ۶۴ نویسه برای متن دکمه دارد و در گوشی
    متن بلند بد نمایش داده می‌شود.
    """
    s = str(txt or "")
    return s if len(s) <= n else s[:n - len(tail)] + tail


def num_or(val, default=0, lo=None, hi=None):
    """
    🔢 تبدیل امن به عدد.

    🎯 جایگزین `int(x)` بی‌محافظ که در اسکن ۹۸ نقطهٔ کرش
       ساخته بود.
    """
    try:
        v = int(str(val).strip())
    except (TypeError, ValueError):
        return default
    if lo is not None and v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


def bar(pct, width=10, full="█", empty="░"):
    """📊 نوار پیشرفت متنی"""
    p = max(0, min(100, int(pct or 0)))
    k = p * width // 100
    return full * k + empty * (width - k)
