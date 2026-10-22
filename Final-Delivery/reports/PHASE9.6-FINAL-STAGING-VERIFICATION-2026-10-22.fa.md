# فاز ۹.۶ — گزارش نهایی: راستی‌آزمایی نهایی، ممیزی خرید فرم‌محور و تثبیت عملیات (۲۰۲۶-۱۰-۲۲)

> این گزارش **مجوز استقرار تولید نیست.** هر ادعا با برچسب وضعیت و مسیر شاهد آمده است. آنچه در این محیط (سندباکس بدون staging، بدون اینترنت خروجی به بله/یوتیوب/آپارات، بدون LibreOffice) قابل اثبات نبود، با همان عنوان و با روش دقیق اجرا روی staging ثبت شده است؛ هیچ موردی «فرض» نشده.

## ۰. شناسنامهٔ تحویل

| مورد | مقدار |
|---|---|
| مخزن / شاخه | `erfan0843/strix` · `arena/840de336-strix` |
| PR | #1 **باز** (`arena/840de336-strix` → `arena/01a0cd72-strix`) — ادغام نشده، پایه تغییر نکرده |
| پایهٔ فاز | `75881f5` (پایان ۹.۵) |
| کامیت‌های ۹.۶ (به ترتیب، هرکدام جداگانه push و روی origin تأیید شد) | `41c21d6` ماتریس · `d1199f9` ممیزی فرم‌محور + سناریوی HTTP · `6c38ab6` آپلود/ذخیره‌سازی/پشتیبان · `bec7fdc` پخش بیرونی + CSP · `4d0239f` گواهی‌ها · `221552c` زمان‌بند/صندوق خروجی · `e6cdea8` رگرسیون + مرورگر · (این گزارش) کامیت ۸ |
| سر مهاجرت | `0036_upload_sessions` (زنجیره `0034 → 0035_notification_dedupe → 0036`) — بدون مهاجرت تازه در ۹.۶ |
| تغییر کد واقعی در ۹.۶ | فقط ۳ مورد: `backend/app.py` (+`report-uri` و سینک `POST /api/csp-report` با لاگ بدون PII)، `admin.js` v144 (نمایش زمان آخرین اجرای زمان‌بند به وقت تهران با UTC خام در `datetime`)، آزمون‌ها (`test_csp_frame_src.py`، `test_scheduled_publish.py`، `admin-rbac.test.mjs`). بقیهٔ حوزه‌ها «ممیزی‌شده، بدون تغییر». |
| ابزارهای تازه (فقط QA؛ روی سرور آزمایشی) | `tools/phase9.6-purchase-e2e.py`، `tools/phase9.6-resumable-upload-http.py`، `tools/phase9.6-browser-evidence.cjs` |
| اسناد | `deployment/PRIVATE-STORAGE-OPERATIONS.fa.md` (§۸ گام جمع‌آوری CSP، §۱۳ زمان‌بند)، `deployment/nora-web.env.example` |
| شواهد | `reports/evidence/phase9.6/` (۱۲ فایل متنی/JSON + `browser/` با ۵۴ تصویر و `browser-checks.txt`) |

برچسب‌ها: **VERIFIED** = اجرای واقعی HTTP/مرورگر روی سرور محلی با دادهٔ مصنوعی · **AUTOMATED_TEST_ONLY** = فقط pytest/jsdom · **SIMULATED** = سرویس بیرونی mock شده · **BLOCKED_EXTERNAL_SERVICE / BLOCKED_EXTERNAL_NETWORK** · **STAGING_REQUIRED** · **OWNER_DECISION_REQUIRED**.

## ۱. رگرسیون نهایی روی کد نهایی (اعداد تازه، `e6cdea8`)

شاهد: `reports/evidence/phase9.6/regression-final.txt`

| مجموعه | فرمان | نتیجه | exit |
|---|---|---|---|
| pytest بک‌اند (SQLite) | `cd website/nora-ui/backend && python -m pytest -q tests` | **359 passed, 4 skipped** (skip: `test_migrations_postgres` بدون `NORA_TEST_POSTGRES_URL`؛ در ردیف بعد پوشش داده شد) | 0 |
| pytest روی PostgreSQL موقت | `python tools/run-postgres-tests.py` | **363 passed** (شامل مهاجرت‌های 0001…0036 روی PG) | 0 |
| mypy | `python -m mypy --config-file backend/mypy.ini backend` | **0 خطا / 73 فایل** | 0 |
| Node/jsdom | `node tools/run-unit-tests.cjs` | **36/36 suite** | 0 |
| ربات بله | `cd bale-bot && python -m pytest -q nora_bot/tests` | **208 passed, 2 skipped** (skip: import بک‌اند در venv ربات؛ LibreOffice نصب نیست) | 0 |
| مرورگر واقعی (Chromium) | `node tools/phase9.6-browser-evidence.cjs` | **44/44 بررسی**، ۵۴ تصویر، ۷ پرسونا × دسکتاپ ۱۲۸۰×۸۰۰ و موبایل ۳۹۰×۸۴۴ | 0 |

## ۲. وضعیت نهایی هر حوزه

### ۲.۱ قرارداد خرید فرم‌محور و ممیزی یکپارچگی — **VERIFIED** (کد بدون تغییر)
شاهد: `evidence/phase9.6/purchase-e2e-http.txt` (۳۷/۳۷)، `integrity-audit-controlled-injection.txt`، مرورگر `d/m-1…5-*`.
- فقط فرم خرید **منتشرشدهٔ** متصل به محصول، مدخل خرید است: محصول پولی بدون فرم → انتشار `409` (`purchase_form_required`)؛ فرم پیش‌نویس کافی نیست؛ قیمت دوم روی محصول `409 commercial_settings_from_form`؛ فرم منتشرشدهٔ دوم برای همان محصول رد می‌شود.
- مسیر قدیمی `POST /api/account/recordings/{id}/orders` → **410**؛ ادعای رایگان روی محصول پولی → 409؛ کیف پول بله بدون پیکربندی امن fail-closed (422/503).
- کارت‌به‌کارت: `awaiting_receipt` → رسید ≠ تأیید (دانلود 403 قبل و بعد از رسید) → تأیید فقط با `receipt_approve` (عضو 403، تکرار 409) → دارنده `206/416` با `x-nora-resource-access: purchased`؛ ردشده/لغو/منقضی هرگز دسترسی نمی‌دهند؛ ارسال تکراری همان سفارش معلق را برمی‌گرداند (پاسخ/پرداخت/دسترسی/اعلان دوم ساخته نمی‌شود).
- IDOR: سفارش دیگران 404، دانلود غریبه 403، کتابخانهٔ غریبه خالی؛ سرآیندها بدون نام فیزیکی/مسیر.
- **خرید ≠ ثبت‌نام ≠ حضور ≠ گواهی** (HTTP + مرورگر): دارنده `viewer.buyer=true` ولی `participation.registered=false/attended=false`، ثبت‌نام ۰، گواهی ۰؛ حاضرِ چک‌این‌شده دانلود `206 access=attended` بدون هیچ ردیف خرید؛ ثبت‌نامیِ بدون حضور → 403.
- توقف فروش: دارندهٔ قبلی می‌ماند، دیگران `off_sale`؛ بازپرداخت فقط `finance` با مرجع (مدیر 403، بدون مرجع 422)؛ لغو دستی با دلیل اجباری و idempotent؛ ورود دوباره/نشست تازه هیچ‌گاه خرید را دوباره نمی‌پرسد.
- ممیزی: پایگاه پاک exit 0 → ۷ تزریق کنترل‌شده روی **کپی آزمایشی** → exit 2 با ۸ یافته (error 6 / warning 1 / info 1)، **sha256 پایگاه پس از اجرا بدون تغییر** (هیچ اصلاح خودکاری نیست)؛ `GET /api/admin/integrity/recordings` فقط‌خواندنی: مالک/مدیر 200 (`read_only=true`)، عضو 403، مهمان 401.
- مشاهدات (نه نقص): لغو دستی حق خریداری‌شده بدون بازپرداخت در ممیزی `paid_payment_without_access` می‌شود (طراحی عمدی برای دیده‌شدن)؛ هر اجرای ابزار e2e یک رویداد «[QA ۹.۶]» روی DB آزمایشی می‌سازد.
- درگاه واقعی بله: **BLOCKED_EXTERNAL_SERVICE** — فقط مسیر محلی/mock آزموده شد (وب‌هوک با پیکربندی خالی 503).

### ۲.۲ فایل‌ها: آپلود ازسرگیرنده، ذخیره‌سازی خصوصی، Range — **VERIFIED** (محلی) / Caddy **STAGING_REQUIRED**
شاهد: `alembic-upgrade-head-sqlite-postgres.txt`، `resumable-upload-http-{24mib,128mib,508mib-near-cap}.txt` (هرکدام ۲۹/۲۹)، `resource-file-replace-prune.txt`.
- `alembic upgrade head` واقعی روی SQLite خالی و PostgreSQL خالی → ۴۰ جدول، سر `0036`، اجرای دوباره بی‌اثر، downgrade/upgrade سالم.
- سلامت ذخیره‌سازی/دیسک پیش از هر آزمون؛ آزمون نزدیک سقف با **۵۰۸ MiB** (سقف `536870912`) فقط پس از تأیید فضای آزاد ≥ ۳× فایل انجام شد. تکه ۴ MiB، `offset_mismatch` 409، checksum غلط 400، `upload_incomplete` 409، سرریز 413، SHA ناهمخوان 422، finalize دوم 410، تمیز بودن `.incoming`، تطابق اندازه + SHA-256، Range 206/416، `/private/` 404، بدون افشای مسیر/شناسهٔ داخلی. جایگزینی فایل بایت‌های قدیمی را هرس می‌کند.
- Range پشت Caddy واقعی و `X-Accel`/دامنه: **STAGING_REQUIRED** (روش: همان ابزار با `NORA_QA_ORIGIN=https://<staging>`).

### ۲.۳ پشتیبان/بازیابی — **VERIFIED** (ایزوله)
شاهد: `backup-restore-cycle-isolated.txt`: سلامت + فضا → snapshot DB و storage → checksum و شمارش → بازیابی به مقصد ایزوله (`/tmp/…/restore-target`، هرگز روی منبع فعال) → سرور دوم روی نسخهٔ بازیابی‌شده: ۵ منبع با sha256 برابر، مهمان 401، عضو بی‌حق 403، دارنده 200، ممیزی صفر یافته. سرور دوم پس از آزمون متوقف شد.

### ۲.۴ پخش بیرونی (یوتیوب/آپارات) و CSP — **AUDITED_UNCHANGED** + پخش زنده **BLOCKED_EXTERNAL_NETWORK**
شاهد: `external-playback-code-review.txt`، `test_csp_frame_src.py` (۵/۵).
- یوتیوب: URL رسمی embed با `enablejsapi=1`؛ وضعیت‌ها فقط از پیام‌های رسمی `onReady/onStateChange/onError` (postMessage)؛ `load` قاب ≠ آماده (`data-embed-playback=unverified` تا `onReady`)؛ کدهای خطای رسمی. آپارات: URL رسمی embed؛ بدون API پخش «قاب بارگذاری شده / پخش تأییدنشده». منبع بیرونی روی محصول پولی بدون تأیید صریح ریسک → 409 (`external_exposure_acknowledgement_required`)؛ سند: embed بیرونی ≠ کنترل دسترسی نورا، DRM ادعا نمی‌شود.
- CSP: همچنان **Report-Only**، `frame-src <فهرست صریح>` بدون `*`؛ تازه: `report-uri /api/csp-report` + سینک با لاگ `nora.csp` (`csp_violation {...}` بدون PII). جمع‌آوری واقعی و هر تصمیم enforce: **STAGING_REQUIRED** (`journalctl -u nora-web | grep csp_violation | sort | uniq -c`)؛ enforce در تولید ممنوع.
- **OWNER_DECISION_REQUIRED:** ماندن روی postMessage (فعلی، بدون اسکریپت بیرونی) یا بارگذاری `iframe_api` رسمی یوتیوب (نیاز به تغییر CSP `script-src`).

### ۲.۵ گواهی‌ها — قواعد **AUTOMATED_TEST_ONLY + VERIFIED (HTTP)**، PDF متنی **STAGING_REQUIRED** (کد بدون تغییر)
شاهد: `certificates-status.txt`، `certificate-pdf-check.json` (exit 2، ۱۶/۱۷؛ تنها `pdf_has_text_layer_office_engine` بدون LibreOffice)، ربات `-k cert` ۱۶ passed / ۲ skipped، مرورگر `*-3-attendee-certificates`, `*-6/7-*-admin-certificates`.
- صدور فقط از `certcenter` ربات؛ `general` و `recording_completion` متمایز؛ حضور فقط با چک‌این؛ استثنای دستی با مجوز+دلیل+عامل+ممیزی؛ تکمیل هرگز خودکار صادر نمی‌شود؛ خرید گواهی نمی‌سازد (پرسونای دارنده: گواهی ۰).
- staging: `apt install libreoffice-writer poppler-utils` → `python tools/certificate-pdf-check.py --json` باید exit 0 و `pdf_has_text_layer_office_engine.ok=true` بدهد.

### ۲.۶ زمان‌بند انتشار و صندوق خروجی — **VERIFIED** (محلی) + تحویل بله **BLOCKED_EXTERNAL_SERVICE**
شاهد: `scheduler-outbox-http.txt`، `test_scheduled_publish.py` (۵/۵)، مرورگر `*-6/7-*-admin-scheduler|outbox`.
- CLI = systemd: `ExecStart=… -m backend.scheduled_publish --once --json` همان `announce_due`؛ اجرای دوبارهٔ CLI روی preview بی‌اثر (`due 0`)؛ تایمر ۵ دقیقه حفظ شد.
- آزمون تازه: سه منبع در یک نوبت (دو محصول، یکی با `publish_at` سال‌ها در گذشته پس از قطع تایمر) در **یک** اجرا و به ترتیب قدیمی‌ترین اعلان می‌شوند؛ اجرای دوم صفر؛ `pending_count` درست. (انتشار با زمان گذشته از خود API بلافاصله توسط مسیر انتشار اعلان می‌شود — رفتار موجود، تأییدشده.)
- پنل: «آخرین اجرا» به وقت تهران/جلالی (`۱۴۰۵/۰۷/۳۰ ۱۳:۵۳` برای `10:23Z`)، UTC خام در `datetime`؛ API همچنان UTC. مجوزها (HTTP): مالک/مدیر 200، عضو 403، مهمان 401؛ retry روی ردیف غیر-failed 409 `notification_not_failed`، عضو 403، مهمان 401؛ run دستی عضو 403، مدیر (`ev_publish`) 200 بدون ردیف تازه. retry حق دسترسی نمی‌سازد (پوشش در `test_failed_notification_retry_requeues_the_same_row_only`).
- مشاهده (نه نقص): هر نوبت `announce_due` یک commit واحد است (همه‌یا‌هیچ؛ خطا ⇒ `ok=false, errors=1` و نوبت بعد دوباره تلاش می‌کند).
- «در صف ≠ تحویل‌شده» در UI حفظ شده؛ تحویل واقعی بله فقط با توکن staging و مخاطب QA.

### ۲.۷ پیش‌نمایش نهایی (کد نهایی + DB آزمایشی) — **VERIFIED** (محلی/سندباکس)
- سرور: uvicorn روی `0.0.0.0:8000` در سندباکس (کد `221552c`/`e6cdea8`)؛ در صورت فعال‌بودن پیش‌نمایش Arena از طریق پراکسی همان پورت در دسترس است؛ در غیر این صورت **فقط localhost سندباکس** است و آدرس عمومی ادعا نمی‌شود.
- مسیر ورود: کارکنان `/login.html?mode=staff&next=admin.html%23dash` (کاربر/رمز **فقط** در فایل gitignore‌شدهٔ `nora-ui/PREVIEW-LOGIN.local.md`؛ هیچ رمزی در گزارش/چت/Git). اعضا با initData امضاشدهٔ آزمایشی (شناسه‌های مصنوعی 91001/91002/91003/91011/91012؛ e2e: 95001–95004).
- صفحات پوشش‌داده‌شده در مرورگر (دسکتاپ+موبایل): خانه + بنر، آرشیو + محصول، فرم خرید، حساب + «رویدادهای من»/«پرداخت‌ها»/«محتوای من»، پخش مجاز و رد دسترسی، مدیریت آرشیو/جلسات/منابع/سفارش‌ها، مدیریت گواهی‌ها، صندوق خروجی + زمان‌بند، پرسش‌وپاسخ و دیدگاه‌ها. مدیر دکمهٔ بازپرداخت ندارد (`finance` فقط مالک — از سرور).

## ۳. موارد باز برای staging/مالک (بدون توقف کار)

| # | مورد | وضعیت | روش دقیق |
|---|---|---|---|
| 1 | درگاه/کیف پول بله واقعی | BLOCKED_EXTERNAL_SERVICE | روی staging با توکن تست: `tools/phase9.6-purchase-e2e.py` + یک پرداخت واقعی کم‌مبلغ؛ بررسی وب‌هوک idempotent و `paid` فقط از رویداد تأییدشده |
| 2 | تحویل اعلان بله | BLOCKED_EXTERNAL_SERVICE | توکن staging + مخاطب QA؛ انتظار: `queued→delivered` فقط پس از پاسخ بله؛ failed → retry یک ردیف |
| 3 | پخش یوتیوب/آپارات زنده | BLOCKED_EXTERNAL_NETWORK | staging با اینترنت: `data-embed-playback` باید با `onReady` به `verified` برود؛ ویدیوی خصوصی → کد خطای رسمی 101/150 |
| 4 | CSP Report-Only | STAGING_REQUIRED | ≥ یک هفته جمع‌آوری؛ `uniq -c`؛ فقط پس از صفر شدن تخلف‌های مشروع، تصمیم enforce (تولید: ممنوع در این فاز) |
| 5 | PDF گواهی با لایهٔ متن | STAGING_REQUIRED | نصب LibreOffice/poppler → `certificate-pdf-check.py` exit 0 |
| 6 | Range/Caddy/دیسک واقعی | STAGING_REQUIRED | همان ابزار آپلود با origin staging؛ `GET /api/admin/storage/health` |
| 7 | تایمر systemd ۵ دقیقه | STAGING_REQUIRED | `systemctl list-timers nora-scheduled-publish`؛ بررسی `last_run.actor=cli` در پنل |
| 8 | postMessage vs `iframe_api` | OWNER_DECISION_REQUIRED | تصمیم مالک؛ گزینهٔ دوم به تغییر CSP نیاز دارد |
| 9 | بازهٔ تایمر (۱–۱۵ دقیقه) | OWNER_DECISION_REQUIRED | پیش‌فرض ۵ دقیقه حفظ شد |

## ۴. آنچه عمداً انجام نشد
ادغام PR #1، تغییر پایهٔ PR، شاخهٔ تازه، استقرار/انتشار، مهاجرت تولید، بازنویسی تاریخچه، حذف/بازنویسی گزارش‌ها و شواهد قبلی، تغییر پیش‌فرض‌های امن (`SameSite=strict`، `NORA_BOT_ALLOW_LEGACY_SQLITE`)، هرگونه قاعده/امتیاز/جدول/API موازی.

## ۵. معیار اتمام (§۱۲)
همهٔ موارد قابل‌آزمون در این محیط با اجرای واقعی تأیید شده و اعداد تازه‌اند؛ موارد وابسته به سرویس بیرونی/staging/تصمیم مالک در جدول §۳ با روش دقیق آمده‌اند. **آمادگی:** کد و آزمون‌ها آمادهٔ staging هستند؛ «code-ready ≠ deploy-ready» — تولید فقط پس از بسته‌شدن ردیف‌های ۱–۷ جدول §۳.
