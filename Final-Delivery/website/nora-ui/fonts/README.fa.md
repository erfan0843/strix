# فونت‌های محلی نورا

این ممیزی هیچ فایل فونتی را جایگزین، تبدیل یا تغییر نداده است. نام، وزن، حق‌نشر و مجوز از جدول `name` خود فایل‌های WOFF2 بررسی شد؛ فونت‌خوانی واقعی Chromium نیز باید همراه تست رابط بررسی شود، نه صرفاً نام `font-family`.

| فایل‌ها | کاربرد و وزن واقعی | مجوز توزیع |
|---|---|---|
| `Estedad-Variable.woff2` | تیترها؛ محور متغیر `wght` از ۱۰۰ تا ۹۰۰ | `LICENSE-Estedad.txt`، SIL OFL 1.1 |
| `Vazirmatn-UI-FD-{Regular,Medium,SemiBold,Bold}.woff2` | متن فارسی؛ وزن‌های ۴۰۰، ۵۰۰، ۶۰۰ و ۷۰۰ | `LICENSE-Vazirmatn.txt`، SIL OFL 1.1 |
| `Nora-Latin-{Regular,Bold}.woff2` | لاتین و شناسه‌های فنی؛ ۴۰۰ و ۷۰۰ | `LICENSE-Nora-Latin.txt`، شرایط Bitstream/DejaVu/Arev |

فونت‌های لاتین جدول مجوز جداگانه ندارند، ولی حق‌نشر Bitstream، Tavmjong Bah و تغییرات DejaVu در خود فایل‌ها ثبت شده است. متن کامل مجوز upstream اکنون همراه آن‌هاست. نام مشتق `Nora Latin` حفظ شده است؛ طبق مجوز، نام‌های رزروشدهٔ upstream نباید به فونت تغییریافته داده شوند.

حق‌نشر استداد در فایل موجود سال ۲۰۲۶ است؛ نسخهٔ مجوز Google Fonts سال ۲۰۲۲ را دارد. هر دو اعلان حفظ شده‌اند و سال فایل دست‌کاری نشده است. متن حقوقی مجوزها عمداً به زبان اصلی باقی مانده؛ این فایل توضیح فارسی آن‌هاست، نه ترجمهٔ جایگزینِ سند حقوقی.

## منبع متن مجوزها

- [استداد در Google Fonts](https://github.com/google/fonts/blob/main/ofl/estedad/OFL.txt)، شناسهٔ blob فایل `a3f7464479be728a1f858574ddb23a46dd83c8c8`.
- [وزیرمتن در Google Fonts](https://github.com/google/fonts/blob/main/ofl/vazirmatn/OFL.txt)، شناسهٔ blob فایل `be66b3824e9772e75141e631695c5256f105fb57`.
- [DejaVu LICENSE](https://github.com/dejavu-fonts/dejavu-fonts/blob/master/LICENSE)، شناسهٔ blob فایل `df52c1709bea171104d41bf084313ea434858423`.

بارگذاری از همین سایت و با `font-display: swap` انجام می‌شود. `Nora Latin` برای کد و شناسه‌ها جداست تا شکل رقم‌ها یا مقدار قابل کپیِ کدهای فنی تغییر نکند. حساب از `font-synthesis: none` استفاده می‌کند؛ وزن موجود مصرف می‌شود، نه ضخیم‌سازی مصنوعی مرورگر.
