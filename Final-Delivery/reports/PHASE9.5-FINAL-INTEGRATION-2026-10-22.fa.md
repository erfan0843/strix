# گزارش نهایی فاز ۹.۵ — ممیزی یکپارچگی، زیرساخت محتوا، گواهی و اعلان (۲۰۲۶-۱۰-۲۲)

- شاخه: `arena/840de336-strix` · PR #1 (باز، به `arena/01a0cd72-strix`؛ ادغام نشده، طبق قاعده)
- مبنا: `786fb4a` (پایان فاز ۹.۴) → سر نهایی: `2c76b31` (کامیت ۹، این گزارش) — SHA ریموت تأیید شد؛ ریزکامیت ۱۰ فقط همین سطر را به‌روز می‌کند
- دامنه: همان Nora UI، همان پایگاه مشترک؛ بازنویسی نشده؛ هیچ ادغام/انتشار/استقرار/مهاجرت تولید/تغییر دادهٔ واقعی انجام نشده است.

## ۱. کامیت‌ها (هر کدام جداگانه push و SHA ریموت تأیید شد)

| # | SHA | محتوا |
|---|---|---|
| ۱ | `3a6af93` | ماتریس ممیزی پیش از کد: `reports/PHASE9.5-AUDIT-MATRIX-2026-10-22.fa.md` (۱۹ قابلیت، وضعیت‌های ۶گانه، منبع حقیقت، مجوز، شکاف، اقدام، آزمون پذیرش) |
| ۲ | `eb399c8` | ممیزی فقط‌خواندنی زنجیرهٔ خرید فرم‌محور: `backend/integrity.py` (۲۱ کد یافته)، `GET /api/admin/integrity/recordings` (`rp_view`)، `tools/recording-access-audit.py` (خروج ۲ با یافته)، کارت پنل؛ هیچ اصلاح خودکاری |
| ۳ | `97342c5` | آپلود قطعه‌ای ازسرگیرنده (پروتکل داخلی محدود) + `GET /api/admin/storage/health` + مهاجرت `0036_upload_sessions` + کلاینت پنل با sha256 افزایشی |
| ۴ | `95f1c28` | چرخهٔ پشتیبان/بازیابی با نشانگر (`storage_verify/snapshot/restore`) + شواهد اجرای واقعی روی preview |
| ۵ | `e733af8` | پخش بیرونی صادقانه: یوتیوب با وضعیت‌های IFrame API روی postMessage، آپارات «تأییدنشده»، تأیید ثبت‌شدهٔ افشای بیرونی برای محصول پولی (۴۰۹ بدون `acknowledge_external_exposure`) |
| ۶ | `27e5672` | ابزار تکرارپذیر PDF واقعی گواهی `bale-bot/tools/certificate-pdf-check.py` (۱۷ بررسی، خروج ۰/۲/۱) + pytest؛ محلی: `STAGING_REQUIRED` |
| ۷ | `d8d7e94` | زمان‌بند انتشار idempotent (`backend/scheduled_publish.py`، CLI `--once`، systemd service+timer)، مانیتور/اجرای دستی پنل، `POST /api/admin/notifications/{id}/retry` |
| ۸ | `7cb4201` | `account.html` با شمارشگر مشترک + `event_schedule` سرور در ثبت‌نام‌های حساب؛ اعلان حاضرانِ چک‌این‌شده؛ `tools/phase9.5-browser-evidence.cjs` + ۱۰ تصویر/۱۲ بررسی |
| ۹ | `2c76b31` | رگرسیون کامل تازه، به‌روزرسانی `deployment/PRIVATE-STORAGE-OPERATIONS.fa.md` (§۶، §۱۱–§۱۴)، همین گزارش |

۶۲ فایل، ‎+۴۶۹۲/‎−۸۹ خط (تا کامیت ۸).

## ۲. رگرسیون کامل تازه (پس از آخرین تغییر کد در `7cb4201`)

| مجموعه | نتیجه | کد خروج |
|---|---|---|
| pytest بک‌اند (SQLite، `backend/tests`) | **۳۵۷ passed, 4 skipped** | ۰ |
| pytest بک‌اند روی PostgreSQL (`tools/run-postgres-tests.py`, pgserver) | **۳۶۱ passed** | ۰ |
| mypy (`backend/mypy.ini`) | **Success: no issues found in 73 source files** | ۰ |
| Node/jsdom (`tools/run-unit-tests.cjs`) | **36/36 suites passed** (از جمله account 134/0، admin 817/0، admin-rbac، admin-recordings، asset-audit) | ۰ |
| ربات بله (`bale-bot/nora_bot/tests`) | **۲۰۸ passed, 2 skipped** (skip: لایهٔ متن PDF بدون LibreOffice) | ۰ |
| مهاجرت‌ها (`test_migrations.py` SQLite رفت‌وبرگشت، `test_migrations_postgres.py`) | داخل دو مجموعهٔ بالا؛ سر زنجیره `0036_upload_sessions` | ۰ |
| مرورگر واقعی (Chromium headless، preview با DB آزمایشی) | **۱۲/۱۲ ✓** — `reports/evidence/phase9.5/browser/browser-checks.txt` + ۱۰ تصویر (۱۲۸۰×۸۰۰ و ۳۹۰×۸۴۴، RTL) | ۰ |
| اسکن راز/مسیر در فایل‌های کامیت‌شده | فقط مقادیر آزمایشی شناخته‌شدهٔ قبلی (`correct-horse-staple-42` در seed آزمایشی، `FAKE_QA_*`)؛ هیچ مسیر `/home/user`، رمز، کوکی یا توکن در شواهد/اسناد | — |

شمارش‌های فازهای قبلی استفاده نشده‌اند؛ همهٔ اعداد بالا از اجرای امروز روی درخت نهایی است.

## ۳. چه چیزی واقعاً ساخته و آزموده شد (به تفکیک: واقعی / شبیه‌سازی / آزموده‌نشده)

### ۳.۱ یکپارچگی فرم‌محور (§۳–§۴)
- **پیاده‌شده و آزموده (واقعی، pytest+PG+preview):** ممیزی فقط‌خواندنی زنجیرهٔ «فرم خرید → پاسخ → پرداخت → دفتر داخلی → دسترسی» با ۲۱ کد یافته (پرداخت بدون دسترسی، دسترسی خرید بدون سفارش/پرداخت معتبر، حساب اشتباه، پرداخت/سفارش تکراری، فرم خرید نامعتبر/منتشرنشده، بازپرداخت بدون لغو، وضعیت فعال منقضی…). هیچ مسیر نوشتن ندارد؛ خروجی فقط شناسه است. محصول رایگانِ منتشرشده بدون فرم خرید **یافته محسوب نمی‌شود** (درست است). اجرای preview: پاک.
- قواعد موجود دست نخورده و دوباره تأیید شدند: قیمت فقط از فرم منتشرشدهٔ معتبر، موفقیت فقط با بررسی سرور، callback تکراری دسترسی دوم نمی‌سازد، محصول پولی بدون فرم منتشرشده منتشر نمی‌شود (در همین فاز یک آزمون تازه همین ۴۰۹ را دوباره دید).

### ۳.۲ ذخیره‌سازی (§۵)
- **واقعی:** آپلود قطعه‌ای با نشست تصادفیِ مقید به عامل، `Upload-Offset/Upload-Checksum`، رد قطعهٔ خارج‌ازترتیب/تکراری، سقف اندازه/قطعه/شمار، sha256 کل، تکمیل یک‌باره، فایل موقت خصوصی، جابه‌جایی اتمیک، انقضای ۲۴ ساعت و ازسرگیری پس از قطع (آزمون HTTP واقعی ۱۲ MiB و نزدیک سقف ۵۱۲ MiB با قطع/ادامه، checksum غلط، هم‌زمانی، بالاتر از سقف، آزادشدن temp، Range پس از تکمیل، جایگزینی/بازگردانی، ردیف↔بایت). گزارش سلامت با مسیر/فضای آزاد/اندازه‌ها/ناقص‌ها/یتیم‌ها/نشانگر آخرین پشتیبان و بررسی. چرخهٔ پشتیبان/بازیابی با `private-storage-backup.py` روی preview اجرا و ثبت شد (`evidence/phase9.5/backup-restore-cycle-preview.txt`).
- **آزموده‌نشده (staging):** فایل چندصدمگابایتی پشت Caddy واقعی و قطع‌ووصل واقعی شبکهٔ مرورگر.

### ۳.۳ ویدیو و CSP (§۶)
- **واقعی (کد+jsdom):** یوتیوب nocookie با `enablejsapi` و وضعیت‌های `loading/ready/playing/paused/buffering/ended/error` فقط از مبدأ رسمی، نگاشت ۱۰۱/۱۵۰/۱۵۳ به پیام صادقانه، بدون autoplay؛ آپارات هرگز «پخش شد» نمی‌گوید؛ انتشار محصول پولی با منبع بیرونی فقط با تأیید صریح و ثبت در ممیزی.
- **آزموده‌نشده (بدون اینترنت در سندباکس):** پخش واقعی هر دو سکو و اثر CSP؛ CSP همچنان Report-Only و `frame-src` خالی. دستور آزمون staging در سند عملیات §۸ و §۱۱.

### ۳.۴ گواهی (§۷)
- بدون تغییر منطق صدور: `certcenter` ربات تنها مرجع؛ دو نوع گواهی جدا؛ صدور دستی فقط با مجوز/دلیل/ممیزی.
- **ابزار آزمون واقعی (کد+اجرا):** `certificate-pdf-check.py` مسیر واقعی صدور/تحویل/تکرار/ابطال/بازگردانی را با آینهٔ سرور اجرا می‌کند؛ محلی ۱۶ بررسی گذشت و ۱ skip (لایهٔ متن) ⇒ خروج ۲ `STAGING_REQUIRED`. **PDF اداری با LibreOffice آزموده‌نشده** (در سندباکس نصب نیست؛ رندر داخلی تصویری است و پاراگراف بلند را نمی‌شکند).

### ۳.۵ اعلان‌ها و انتشار زمان‌بندی‌شده (§۸)
- **واقعی (pytest+PG+مرورگر روی preview):** زمان‌بند idempotent فقط «اعلان» می‌دهد؛ محتوای آینده پیش از `publish_at` نه در صفحه و نه در API دیده شد؛ اجرای دستی پس از موعد دقیقاً ۱ اعلان ساخت و اجرای دوم ۰؛ دارنده دقیقاً +۱ اعلان دید. شکاف واقعی ۹.۴ بسته شد: حاضرانِ چک‌این‌شدهٔ محصول با `attendee_access` (دسترسی مشتق، بدون ردیف access) هم اعلان می‌گیرند؛ ثبت‌نامیِ غایب نمی‌گیرد. تلاش دوبارهٔ اعلان ناموفق همان ردیف را به صف برمی‌گرداند (۰ تلاش، بدون ردیف تازه، بدون ادعای تحویل)، فقط با `ev_publish`، با ممیزی؛ ۴۰۹ برای تحویل‌شده/غیرناموفق/بدون‌بله. مانیتور پنل وضعیت `stalled` را وقتی تایمر اجرا نشده نشان می‌دهد.
- **شبیه‌سازی‌شده:** وضعیت «شکست نهایی ربات» برای ردیف آزمون با دست روی DB آزمایشی preview تزریق شد (در `browser-checks.txt` ثبت است).
- **آزموده‌نشده:** تایمر systemd روی سرور واقعی؛ تحویل واقعی بله (وضعیت رسمی: «صف و ساختار اعلان»).

### ۳.۶ حساب و پنل (§۹–§۱۰)
- **واقعی:** `account.html` اکنون `countdown.css?v=2` و `countdown.js?v=3` را دارد و پس از رندر `mount` می‌کند (پیش از این شمارشگر هرگز روی حساب فعال نمی‌شد). ثبت‌نام‌های حساب فیلد افزودنی `event_schedule` از سرور می‌گیرند (همان قاعدهٔ `registration_state`، ساعت سرور)؛ لغو/تعویق برچسب می‌گیرد و شمارش ندارد؛ رویداد برگزارشده شمارش ندارد؛ بدون زمان سرور چیزی ساخته نمی‌شود (مرورگر موبایل/دسکتاپ ثبت شد). پنل: کارت زمان‌بند، دکمهٔ تلاش دوباره، کارت ممیزی، کارت سلامت ذخیره‌سازی — همه از API سرور و با مجوز سرور (گست ۴۰۱، عضو ۴۰۳ روی HTTP واقعی).
- دسترسی‌ها در بک‌اند اعمال و آزموده شده؛ پنهان‌کردن دکمه مبنای کنترل نیست.

## ۴. فایل‌های اصلی تغییر/افزوده‌شده
- بک‌اند: `backend/integrity.py` (نو)، `backend/upload_sessions.py` (نو)، `backend/scheduled_publish.py` (نو)، `backend/storage.py`، `backend/recordings.py` (`active_holders`, `attended_account_ids`)، `backend/event_interaction.py` (`announced_at`)، `backend/models.py`، `backend/migrations/versions/0036_upload_sessions.py`، `backend/app.py` (مسیرهای integrity/storage-health/upload-sessions/scheduled-publish/retry، `event_schedule`، تأیید افشای بیرونی).
- آزمون‌های بک‌اند نو: `test_recording_integrity_audit.py`, `test_resumable_upload.py`, `test_scheduled_publish.py` (+ به‌روزرسانی `test_private_storage`, `test_video_sources`, `test_notifications_outbox`, `test_event_registration_gate`, `test_identity_scoped_form_history`, `test_migrations*`).
- فرانت: `owner-api.js` v122، `admin.js` v143، `event-interaction.js` v8، `account.js` v137، `account.html`، `admin.html`، `event.html` و بامپ‌های نسخه در صفحات دارای `owner-api.js`؛ آزمون‌های jsdom مربوط.
- ربات: `bale-bot/tools/certificate-pdf-check.py`, `nora_bot/tests/test_certificate_pdf_real_engine.py`.
- استقرار/اسناد: `deployment/nora-scheduled-publish.service`, `.timer`, `deployment/PRIVATE-STORAGE-OPERATIONS.fa.md` (§۶ بازنویسی، §۱۱–§۱۴ نو).
- ابزار/شواهد: `tools/recording-access-audit.py`, `tools/private-storage-backup.py`, `tools/phase9.5-browser-evidence.cjs`, `reports/evidence/phase9.5/*`.

## ۵. محدودیت‌ها و «کدآماده ≠ آزمودهٔ محلی ≠ آمادهٔ استقرار»

| | وضعیت |
|---|---|
| کد + آزمون خودکار (SQLite، PostgreSQL، mypy، jsdom، ربات) | ✅ آزمودهٔ محلی |
| مرورگر واقعی روی سرور uvicorn + DB آزمایشی preview | ✅ آزمودهٔ محلی (داده‌های مصنوعی) |
| پخش واقعی یوتیوب/آپارات، CSP enforce | ⛔ آزموده‌نشده (بدون اینترنت) |
| PDF اداری گواهی با LibreOffice، `pdftotext` | ⛔ نیازمند staging |
| تایمر systemd، Caddy واقعی، آپلود چندصدمگابایتی | ⛔ نیازمند staging |
| تحویل واقعی بله | ⛔ آزموده‌نشده |
| مهاجرت `0036` روی تولید | ⛔ انجام نشده (طبق قاعده) |

یادداشت‌های صادقانه دربارهٔ preview: پایگاه preview با `create_all` ساخته شده و `alembic_version` ندارد؛ شکل `0036` روی آن **با دست** اعمال شد (روی تولید باید `alembic upgrade head` اجرا شود). اعتبارنامهٔ آزمایشی preview در میانهٔ فاز چرخانده شد و فقط در فایل محلی خارج از Git است؛ هیچ رمزی در گزارش یا چت نیامده است.

## ۶. تصمیم‌هایی که به مالک نیاز دارند (کار متوقف نشد؛ پیش‌فرض‌های امن اعمال شد)
1. سقف اندازهٔ فایل تولید و ظرفیت دیسک (پیش‌فرض ۵۱۲ MiB نگه داشته شد؛ سقف پراکسی باید هم‌خوان باشد).
2. پذیرش ریسک منبع بیرونی برای هر محصول پولی (اکنون اجباری و ثبت‌شده در ممیزی).
3. نصب LibreOffice روی سرور ربات برای PDF واقعی.
4. زمان enforce کردن CSP پس از آزمون staging.
5. بازهٔ تایمر زمان‌بند (پیش‌فرض ۵ دقیقه).

## ۷. دستورهای آزمون staging (خلاصه)
```
# وب
alembic -c backend/alembic.ini upgrade head
python -m backend.scheduled_publish --once --json          # خروج 0
python tools/recording-access-audit.py --json             # خروج 0 = بدون یافته
python tools/private-storage-backup.py verify             # نشانگر storage_verify
systemctl enable --now nora-scheduled-publish.timer && journalctl -u nora-scheduled-publish -n 20
# ربات (با LibreOffice نصب‌شده)
python tools/certificate-pdf-check.py --json              # باید خروج 0 بدهد، نه 2
# مرورگر واقعی (پس از تنظیم NORA_CSP_FRAME_SRC و Report-Only)
NORA_QA_ORIGIN=https://<staging> node tools/phase9.5-browser-evidence.cjs <خروجی>
```
