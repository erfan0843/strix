# فاز ۹.۶ — گزارش وضعیت آغازین و ماتریس staging (۲۰۲۶-۱۰-۲۲)

- مخزن `erfan0843/strix` · شاخه `arena/840de336-strix` · PR #1 باز (به `arena/01a0cd72-strix`) · HEAD آغازین `75881f5` = origin · working tree تمیز.
- سر مهاجرت Alembic: `0036_upload_sessions` (زنجیره `0034_private_storage → 0035_notification_dedupe → 0036`). سرویس‌ها: `nora-web.service`, `nora-bot.service`, `nora-scheduled-publish.service/.timer` (۵ دقیقه).
- اسناد خوانده‌شده: گزارش‌های ۹.۱–۹.۵، ماتریس ۹.۵، `PRIVATE-STORAGE-OPERATIONS.fa.md` §۱–§۱۴، `PRIVATE-VIDEO-STORAGE-REQUIREMENTS.fa.md`.

## محیط واقعاً موجود (نه فرضی)

| نیاز | وضعیت |
|---|---|
| staging با Caddy، دامنه، systemd | **ندارد.** تنها محیط اجرا: سندباکس با uvicorn روی `0.0.0.0:8000` + DB آزمایشی SQLite (`/…/nora-preview`) و ذخیره‌سازی خصوصی محلی. این «preview» است، نه staging. |
| اینترنت خروجی | فقط github/pypi/npm. یوتیوب/آپارات/بله دست‌نیافتنی ⇒ `BLOCKED_EXTERNAL_NETWORK`. |
| LibreOffice / poppler | نصب‌نشدنی (apt بدون شبکه) ⇒ `STAGING_REQUIRED`. |
| توکن بله واقعی / مخاطب QA | وجود ندارد ⇒ `BLOCKED_EXTERNAL_SERVICE`. |
| PostgreSQL | pgserver یک‌بارمصرف برای آزمون؛ کافی برای `alembic upgrade head` واقعی روی PG خالی. |
| دیسک آزاد | ≈۱۸ GiB ⇒ آزمون آپلود چندده‌مگابایتی ممکن؛ آزمون نزدیک سقف ۵۱۲ MiB فقط با بررسی فضای آزاد پیش از اجرا. |

## ماتریس وضعیت (پیش از کار؛ ستون «هدف ۹.۶» = بهترین وضعیت قابل‌دستیابی در این محیط)

برچسب‌ها: `VERIFIED` (اجرای واقعی HTTP/مرورگر روی سرور محلی با دادهٔ مصنوعی) · `AUTOMATED_TEST_ONLY` · `SIMULATED` (سرویس بیرونی mock) · `BLOCKED_EXTERNAL_SERVICE` · `STAGING_REQUIRED` · `OWNER_DECISION_REQUIRED`.

| # | بخش | وضعیت ورودی (پایان ۹.۵) | هدف ۹.۶ در این محیط | اقدام برنامه‌ریزی‌شده |
|---|---|---|---|---|
| ۱ | قرارداد فرم‌محور خرید (فرم منتشرشده تنها ورودی، قیمت/روش از فرم، `recording_orders` دفتر داخلی، بدون مسیر موازی) | AUTOMATED_TEST_ONLY + VERIFIED (مرورگر ۹.۱–۹.۳) | VERIFIED (HTTP واقعی روی preview، ۱۲ سناریوی §۳) | اسکریپت HTTP سرتاسری با پرسوناها؛ بدون تغییر کد مگر نقص واقعی |
| ۲ | ابزار ممیزی `recording-access-audit.py` + API فقط‌خواندنی | AUTOMATED_TEST_ONLY (تزریق در pytest) + preview پاک | VERIFIED (اجرا روی نسخهٔ آزمایشی با تزریق کنترل‌شده، اثبات بدون‌نوشتن با hash پایگاه) | اجرای واقعی CLI، ثبت خروجی و hash قبل/بعد |
| ۳ | پرداخت کیف پول بله | SIMULATED (وب‌هوک mock در pytest) | SIMULATED | سرویس واقعی ندارد؛ فقط منطق سرور |
| ۴ | کارت‌به‌کارت تا تأیید مسئول | VERIFIED (۹.۲) | VERIFIED (تکرار روی کد نهایی) | در اسکریپت E2E |
| ۵ | مهاجرت `0036` | AUTOMATED_TEST_ONLY (round-trip) | VERIFIED روی SQLite و PG خالی (`alembic upgrade head` واقعی) | اجرای واقعی و ثبت خروجی |
| ۶ | آپلود ازسرگیرنده (قطع/ادامه/offset/checksum/تکمیل یک‌باره/پاک‌سازی temp/عدم افشای مسیر) | AUTOMATED_TEST_ONLY (HTTP داخل pytest ۱۲ MiB) | VERIFIED روی uvicorn واقعی با فایل بزرگ‌تر؛ نزدیک سقف فقط اگر دیسک اجازه دهد | اسکریپت HTTP؛ بررسی `df` قبل از آن |
| ۷ | Range 206/416 و بدون‌مجوز | VERIFIED (۹.۴ بدون Caddy) | VERIFIED بدون Caddy؛ پشت Caddy `STAGING_REQUIRED` | تکرار روی کد نهایی |
| ۸ | پخش یوتیوب (IFrame API) | BLOCKED_EXTERNAL_NETWORK | BLOCKED_EXTERNAL_NETWORK + بازبینی کد در برابر قرارداد رسمی | گزارش؛ بدون کد حدسی |
| ۹ | پخش آپارات | BLOCKED_EXTERNAL_NETWORK | BLOCKED_EXTERNAL_NETWORK | گزارش |
| ۱۰ | ریسک منبع بیرونی محصول پولی (هشدار + تأیید ثبت‌شده) | AUTOMATED_TEST_ONLY + jsdom | VERIFIED (HTTP: ۴۰۹ بدون تأیید، ممیزی با تأیید) | در اسکریپت E2E |
| ۱۱ | CSP Report-Only | کد VERIFIED، جمع‌آوری نقض ندارد | AUTOMATED_TEST_ONLY برای سرآیند؛ جمع‌آوری نقض `STAGING_REQUIRED` | افزودن `report-uri` + نقطهٔ دریافت گزارش بدون PII (کم‌ریسک) |
| ۱۲ | گواهی حضور / پایان محتوا (تمایز، شرط حضور، صدور دستی با دلیل و ممیزی) | AUTOMATED_TEST_ONLY + ربات ۲۰۸ | AUTOMATED_TEST_ONLY + VERIFIED در مرورگر (خرید ⇏ حضور/گواهی) | پرسونای مرورگر |
| ۱۳ | PDF واقعی گواهی | STAGING_REQUIRED (خروج ۲) | STAGING_REQUIRED | اجرای دوبارهٔ ابزار، ثبت خروج ۲ |
| ۱۴ | پشتیبان/بازیابی | VERIFIED روی preview (۹.۵) | VERIFIED (چرخهٔ کامل با DB + checksum + تفاوت قبل/بعد در مقصد ایزوله) | اجرای واقعی |
| ۱۵ | زمان‌بند (idempotent، چند مورد در یک اجرا، UTC/تهران، CLI = systemd) | VERIFIED (یک منبع) | VERIFIED برای چند منبع و اجرای مکرر؛ تایمر systemd `STAGING_REQUIRED` | آزمون چندموردی + نمایش تهران در پنل اگر لازم |
| ۱۶ | صندوق خروجی و retry با مجوز | VERIFIED | VERIFIED (تکرار) | — |
| ۱۷ | تحویل واقعی بله | BLOCKED_EXTERNAL_SERVICE | BLOCKED_EXTERNAL_SERVICE | — |
| ۱۸ | پرسوناهای مرورگر (۷ نقش) | بخشی در ۹.۳–۹.۵ | VERIFIED روی کد نهایی (دسکتاپ+موبایل) | اسکریپت شواهد ۹.۶ |
| ۱۹ | پیش‌نمایش برای مرورگر کاربر | URL e2b پروکسی‌شده | ارائه با مسیر ورود؛ محدودیت کوکی ثبت می‌شود | — |

## تصمیم‌های مالک (کار متوقف نمی‌شود)
1. تهیهٔ staging واقعی (Caddy + systemd + LibreOffice + توکن بله QA) — بدون آن ردیف‌های ۸، ۹، ۱۳، ۱۷ و بخش Caddy ردیف ۷ باز می‌مانند.
2. بارگذاری اسکریپت رسمی `iframe_api` یوتیوب در صفحه (اسکریپت شخص‌ثالث) در برابر کانال postMessage فعلی (همان قرارداد رویداد، بدون اسکریپت بیرونی).
3. زمان enforce کردن CSP پس از جمع‌آوری گزارش staging.
