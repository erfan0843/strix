# راهنمای عملیاتی حافظهٔ خصوصی فایل‌ها (فاز ۹.۴)

این سند مکمل `PRIVATE-VIDEO-STORAGE-REQUIREMENTS.fa.md` (الزامات) است و می‌گوید آنچه در کامیت ۲ فاز ۹.۴ **پیاده و آزموده** شده چگونه راه‌اندازی، پشتیبان‌گیری و بازیابی می‌شود. «پیاده‌شده» با «روی سرور تولید آزموده‌شده» یکی نیست؛ بخش ۷ می‌گوید چه چیزی هنوز فقط روی محیط آزمون اثبات شده است.

## ۱. چه چیزی ساخته شد

| مورد | وضعیت |
|---|---|
| رابط `backend/storage.py` (`PrivateStorage` Protocol) + پیاده‌سازی `LocalPrivateStorage` (دیسک محلی) | پیاده‌شده، آزموده با pytest |
| S3 / MinIO / CDN | **پیاده نشده** (بدون محیط آزمون واقعی ادعایی نمی‌شود)؛ رابط برای افزودن آماده است |
| مسیر ریشه از `NORA_PRIVATE_STORAGE_DIR`؛ باید بیرون `nora-ui/` باشد وگرنه برنامه بالا نمی‌آید (`storage_inside_webroot`) | آزموده |
| نام فیزیکی سروری `YYYY/MM/<uuid4 hex>`؛ نام فایل کاربر فقط در DB برای `Content-Disposition` | آزموده |
| نوشتن اتمیک: `.incoming/<uuid>.part` → `fsync` → `os.replace`؛ فایل نیمه‌کاره هرگز کلید نمی‌گیرد | آزموده (قطع اتصال وسط آپلود) |
| مجوزها `0700` پوشه / `0600` فایل | آزموده |
| سقف هر فایل `NORA_PRIVATE_STORAGE_MAX_MIB` (پیش‌فرض ۵۱۲)؛ هنگام استریم اعمال، ۴۱۳ + پاک‌شدن `.part` | آزموده |
| آپلود استریمی بدون جمع‌کردن کل بدنه در حافظه | آزموده با سرور واقعی uvicorn، فایل ۴۸ MiB، اوج تخصیص پایتون < ۱۲ MiB |
| پخش با `Range` (۲۰۶ / ۴۱۶ / چندبازه‌ای ⇒ کل فایل) و `Content-Encoding: identity`؛ خواندن تکه‌ای ۲۵۶ KiB | آزموده با سرور واقعی |
| بررسی دسترسی در هر درخواست (۴۰۱ مهمان، ۴۰۳ غریبه، ۴۰۳ بلافاصله پس از لغو) | آزموده |
| جایگزینی فایل: کلید تازه، فایل قبلی فقط **پس از commit** پاک می‌شود، ردیف‌های دسترسی دست نمی‌خورند، audit `event_resource.file` + `event_resource.file_pruned` | آزموده |
| وضعیت ذخیره‌سازی در پنل (`ready / empty / missing / size_mismatch / storage_not_configured`) بدون مسیر فیزیکی | آزموده (API + jsdom) |
| فایل گم‌شده: پنل `missing`، انتشار منبع/محصول ۴۰۹، بیننده بایت نمی‌گیرد | آزموده |
| ابزار `tools/private-storage-backup.py` (`verify` / `snapshot` / `restore`) | آزموده (snapshot → حذف پوشه → restore → verify) |
| آپلود قطعه‌قطعهٔ ازسرگیرنده (resumable) | **پیاده نشده** — بخش ۶ |

## ۲. راه‌اندازی روی سرور

```bash
# ۱) پوشه بیرون ریشهٔ وب، فقط برای کاربر سرویس
sudo install -d -o nora -g nora -m 0700 /var/lib/nora/private-store

# ۲) متغیرهای محیطی سرویس وب (همان فایل env که uvicorn می‌خواند)
NORA_PRIVATE_STORAGE_DIR=/var/lib/nora/private-store
NORA_PRIVATE_STORAGE_MAX_MIB=512

# ۳) مهاجرت (روی محیط آزمون اول؛ هیچ اجرای خودکار روی تولید در این مخزن انجام نشده)
cd Final-Delivery/website/nora-ui/backend && alembic upgrade head   # head = 0034_private_storage
```

نکته‌ها:

* تا وقتی `NORA_PRIVATE_STORAGE_DIR` خالی است **هیچ رفتاری عوض نمی‌شود**: سقف ۸ MiB و ذخیره در DB مانند فاز ۸/۹.
* پس از تنظیم، همهٔ بارگذاری‌های تازه (حتی کوچک) روی دیسک می‌روند؛ ردیف‌های قدیمی داخل DB بدون مهاجرت داده همچنان سرو می‌شوند. جابه‌جایی ردیف‌های قدیمی به دیسک عمداً خودکار نیست.
* `max_request_bytes` عمومی (۶۴ KB) روی این مسیر اعمال نمی‌شود؛ سقف این مسیر فقط `NORA_PRIVATE_STORAGE_MAX_MIB` است.

### چرا پیش‌فرض ۵۱۲ MiB؟

«۲ GiB» در سند الزامات فقط مثال بود. پیش‌فرض باید با سه محدودیت واقعی بخواند:

1. **دیسک:** با یک دیسک معمولی VPS (۴۰–۸۰ GB) و پشتیبان روزانه، ۵۱۲ MiB برای یک ویدیوی ۶۰–۹۰ دقیقه‌ای با بیت‌ریت ۷۲۰p کافی است و اجازه می‌دهد ده‌ها جلسه بدون پر شدن دیسک نگه داشته شود.
2. **پراکسی/مرورگر:** آپلود از مرورگر یک درخواست `PUT` است (ازسرگیرنده نیست). روی پیوند ۵ Mbps، ۵۱۲ MiB ≈ ۱۵ دقیقه؛ بالاتر از آن احتمال قطع اتصال و تکرار آپلود زیاد می‌شود. Caddy به‌طور پیش‌فرض بدنه را محدود نمی‌کند؛ اگر `request_body max_size` گذاشتید باید ≥ همین مقدار باشد (نمونه در `Caddyfile`).
3. **پشتیبان‌گیری:** snapshot فایل‌ها کپی کامل است؛ هر فایل بزرگ‌تر زمان پشتیبان‌گیری و بازیابی را خطی زیاد می‌کند.

برای فایل‌های بزرگ‌تر، مقدار را آگاهانه (تا ۸۱۹۲) بالا ببرید و قبلش دیسک آزاد و زمان پشتیبان‌گیری را اندازه بگیرید. پنل مقدار واقعی را از سرور می‌خواند و عدد ثابتی ندارد.

## ۳. پشتیبان‌گیری (جدا از پایگاه داده)

پشتیبان DB **ویدیوها را ندارد**؛ فقط `event_resources.storage_key` را دارد. هر برنامهٔ پشتیبان‌گیری باید دو نیمه را با هم نگه دارد:

```bash
export NORA_DATABASE_URL=...            # همان مقدار سرویس
export NORA_PRIVATE_STORAGE_DIR=/var/lib/nora/private-store

# راستی‌آزمایی: ردیف‌های DB ↔ فایل‌ها (خروجی JSON؛ exit 1 اگر فایلِ ارجاع‌شده‌ای گم/ناهم‌اندازه باشد)
python3 tools/private-storage-backup.py verify            # سریع: وجود + اندازه
python3 tools/private-storage-backup.py verify --hash     # کند: sha256 هر فایل

# snapshot: فقط فایل‌های commit‌شده (هرگز .incoming) + MANIFEST.json با sha256
python3 tools/private-storage-backup.py snapshot /backup/nora-files/$(date +%F)
```

ترتیب پیشنهادی: اول `pg_dump`/کپی SQLite، بعد `snapshot`. چون کلیدها هرگز بازاستفاده نمی‌شوند و فایل‌ها پس از commit تغییر نمی‌کنند، snapshot کمی «جدیدتر» از DB بی‌خطر است (فایل اضافی = orphan قابل گزارش)، ولی عکس آن (DB جدیدتر از snapshot) یعنی ردیف‌هایی که فایل ندارند — `verify` همین را نشان می‌دهد.

`verify` همچنین `orphans` (فایل بدون ردیف) و `stale_parts` (آپلودهای نیمه‌کارهٔ قدیمی در `.incoming`) را **فقط فهرست می‌کند**. هیچ حذف خودکار و هیچ زمان‌بندی پاک‌سازی وجود ندارد؛ حذف تصمیم انسانی است و باید در گزارش عملیات ثبت شود.

## ۴. بازیابی و آزمون بازیابی

```bash
python3 tools/private-storage-backup.py restore /backup/nora-files/2026-10-22
python3 tools/private-storage-backup.py verify
```

* `restore` هر فایل را با sha256 مانیفست می‌سنجد، فایل موجود را بدون `--force` رونویسی نمی‌کند و کلید نامعتبر را رد می‌کند.
* **آزمون بازیابی روی محیط آزمون** در `tests/test_private_storage.py::test_backup_snapshot_restores_files_that_rows_point_at` خودکار شده است: snapshot → حذف کامل پوشه → پنل `missing` → restore → پنل `ready`. این آزمون روی سرور تولید اجرا نشده و نباید شود؛ روی staging با دادهٔ غیرواقعی تکرارش کنید و نتیجه را در گزارش استقرار ثبت کنید.

## ۵. مهاجرت ۰۰۳۴ و بازگشت

* ارتقا: ستون `storage_key` + گشودن قید `ck_event_resources_size` (سقف ۸ MiB فقط برای ردیف‌های داخل DB).
* بازگشت: اگر ردیفی با `content_size > 8 MiB` وجود داشته باشد، `downgrade` **خطا می‌دهد و چیزی پاک نمی‌کند**. برای بازگشت باید آن ردیف‌ها آگاهانه حذف/جایگزین شوند. ستون حذف می‌شود ولی فایل‌های روی دیسک دست نمی‌خورند؛ پیش از هر بازگشت یک `snapshot` تأییدشده بگیرید.
* روی SQLite و PostgreSQL (pgserver) در CI محلی آزموده شد.

## ۶. آپلود قطعه‌قطعهٔ ازسرگیرنده (کامیت ۳ فاز ۹.۵ — پروتکل داخلی محدود، نه tus)

مسیر تک‌درخواستی (`PUT …/file`) حفظ شده و برای فایل‌های ≤ ۸ MiB یا وقتی ذخیره‌سازی دیسک تنظیم نیست همان مسیر استفاده می‌شود. برای فایل‌های بزرگ‌تر روی دیسک، پنل خودکار از نشست آپلود استفاده می‌کند:

* `POST /api/admin/events/{ev}/resources/{rid}/upload-sessions` `{size, sha256?, file_name}` → `201 {id, status, offset, expected_size, chunk_bytes (۴ MiB), max_chunk_bytes (۸ MiB), chunk_count, expires_at, resumed}`؛ شناسهٔ نشست تصادفی است و به اقدام‌کنندهٔ سازنده قفل است؛ همهٔ مراحل مجوز `ev_create` و CSRF دارند.
* `PATCH …/upload-sessions/{sid}` با بدنهٔ خام + `Upload-Offset` (+ اختیاری `Upload-Checksum: sha256 <hex>`): قطعهٔ خارج‌ازترتیب/تکراری ⇒ `409 offset_mismatch` (پاسخ offset درست را می‌گوید تا کلاینت از همان‌جا ادامه دهد)، checksum نادرست ⇒ `400 chunk_checksum_mismatch`، قطعهٔ بزرگ‌تر از سقف یا شمار قطعهٔ بیش از حد ⇒ `413`، نشست منقضی/کامل/لغوشده ⇒ `410 upload_session_<status>`.
* `POST …/upload-sessions/{sid}/complete` `{sha256?}`: فقط وقتی `offset == expected_size`؛ sha256 کل فایل بررسی، سپس جابه‌جایی اتمیک از `.incoming` به مسیر نهایی و به‌روزرسانی ردیف منبع در یک تراکنش؛ تکمیل دوباره ⇒ `410`. `DELETE …/{sid}` نشست را لغو و فایل موقت را حذف می‌کند.
* سقف‌ها: همان `NORA_PRIVATE_STORAGE_MAX_MIB` برای اندازهٔ اعلام‌شده (قبل از دریافت حتی یک بایت)، انقضای نشست ۲۴ ساعت، فایل موقت خصوصی (`.incoming/<sid>.part`) تا پایان؛ `GET …/upload-sessions/{sid}` برای ازسرگیری پس از قطع اتصال. پاک‌سازی نشست‌های منقضی هرگز فایل معتبر یا دسترسی فعالی را حذف نمی‌کند.
* گزارش سلامت: `GET /api/admin/storage/health` (`rp_view`) → مسیر تنظیم‌شده، فضای آزاد/قابل‌استفاده، مجموع اندازهٔ ذخیره‌شده، فایل‌های موقت ناقص، ردیف‌های بدون فایل، فایل‌های یتیم، نشانگرهای آخرین پشتیبان/بازیابی/بررسی (`markers`) و `state ∈ ok|warning|error|not_configured|inline_only`. پنل: «کاربران → گزارش سرور → سلامت ذخیره‌سازی».
* آزموده‌شده (pytest، فایل > ۸ MiB و نزدیک سقف): آپلود کامل، قطع و ازسرگیری، checksum غلط، دو نشست هم‌زمان، بالاتر از سقف، آزادشدن فایل موقت، دانلود Range پس از تکمیل، جایگزینی/بازگردانی، تطابق ردیف↔بایت. **آزموده‌نشده:** قطع‌ووصل واقعی مرورگر روی پیوند کند و فایل چندصدمگابایتی پشت Caddy (نیازمند staging).

## ۷. مرز صادقانهٔ وضعیت

| | وضعیت |
|---|---|
| کد و آزمون خودکار (pytest SQLite + PostgreSQL، سرور واقعی uvicorn، jsdom پنل) | ✅ |
| اجرا روی محیط staging با Caddy واقعی و مرورگر واقعی (آپلود چندصدمگابایتی، پخش با seek) | ⛔ آزموده‌نشده در این مخزن |
| اجرای مهاجرت روی تولید / تنظیم env تولید | ⛔ انجام نشده (خارج از اختیار این فاز) |
| S3/CDN، DRM، transcoding، HLS | ⛔ وجود ندارد و ادعایی نمی‌شود |

## ۸. ویدیوی یوتیوب/آپارات و CSP (کامیت ۳ فاز ۹.۴)

وضعیت کد (بدون تغییر منطقی در این فاز): `backend/video_sources.py` فقط شناسهٔ اعتبارسنجی‌شدهٔ سرور را می‌پذیرد و نشانی رسمی embed همان سکو (`youtube-nocookie.com/embed/…`, `aparat.com/video/video/embed/videohash/…`) را می‌سازد؛ هیچ HTML/iframe ذخیره نمی‌شود؛ قاب در `event-interaction.js` با `data-embed-playback="unverified"` می‌آید یعنی «بارگذاری قاب ≠ پخش». محتوای Unlisted/خصوصی سکو همچنان بیرون کنترل نوراست و DRM نیست (هشدار در پنل برای محصول پولی موجود است).

چه چیزی در این مخزن **آزموده نشد و نمی‌شود**: پخش واقعی در مرورگر با اینترنت (سندباکس دسترسی خارجی ندارد). بنابراین IFrame API/رویداد پخش پیاده نشد (رویداد ساختگی ممنوع).

روش آزمون staging پیش از هر ادعای «پخش می‌شود»:

1. در env وب: `NORA_CSP_FRAME_SRC="'self' https://www.youtube-nocookie.com https://www.aparat.com"` و `NORA_CSP_REPORT_ONLY=1`؛ سرویس را دوباره بالا بیاورید. (نیازی به تغییر Caddy نیست؛ سیاست را دو جا نفرستید.)
2. با یک حساب دارندهٔ دسترسی، `event.html` رویدادی با یک منبع یوتیوب و یک منبع آپارات، سپس `account.html` و پیش‌نمایش منبع در `admin.html` را در Chrome/Firefox باز کنید.
3. در کنسول مرورگر `securitypolicyviolation` و پیام‌های CSP را ببینید؛ اگر پخش‌کنندهٔ قدیمی رسانهٔ رویداد (`ui.js`) با vimeo/dailymotion در دادهٔ واقعی هست باید به فهرست اضافه شود.
   - فاز ۹.۶: سیاست همراه `report-uri /api/csp-report` می‌رود؛ مرورگرها هر نقض را به همین مسیر POST می‌کنند و سرور فقط **یک خط لاگ بدون PII** می‌نویسد (`nora.csp` سطح WARNING: `directive`, `blocked` = فقط مبدأ، `document` = فقط مسیر، `disposition`). هیچ چیزی ذخیره نمی‌شود. جمع‌آوری روی staging: `journalctl -u nora-web | grep csp_violation | sort | uniq -c` — مبدأهای تکرارشوندهٔ مرتبط با پخش (مثلاً `https://www.youtube.com` برای اسکریپت‌های داخلی قاب nocookie) «لازم» و بقیه «مشکوک» گزارش شوند؛ `*` یا مبدأ نامرتبط هرگز به allowlist اضافه نشود. هر سناریو (با/بی یوتیوب، با/بی آپارات، صفحهٔ ورود، سایر قاب‌ها) جداگانه باز شود.
4. فقط پس از صفر شدن گزارش‌ها: `NORA_CSP_REPORT_ONLY=0`. سرآیند فقط روی HTML می‌رود؛ پاسخ‌های فایل CSP `sandbox` خودشان را نگه می‌دارند و `X-Frame-Options: SAMEORIGIN` تغییر نمی‌کند.
5. نتیجه را در گزارش استقرار با تاریخ، مرورگر و شناسهٔ ویدیوهای آزمون‌شده ثبت کنید. تا آن زمان وضعیت رسمی: **«قاب ساخته می‌شود؛ پخش زنده آزموده‌نشده»**.

## ۹. اعلان‌ها: صف، تکرارناپذیری و بازبینی در پنل (کامیت‌های ۵ و ۶ فاز ۹.۴)

- یک مسیر نوشتن: `backend/notifications.py` → `queue(...)`. هر ردیف `user_notifications` یک `dedupe_key` یکتا دارد (مهاجرت `0035_notification_dedupe`؛ ردیف‌های قدیمی `NULL` می‌مانند و دست نمی‌خورند؛ `downgrade` فقط ستون‌ها را برمی‌دارد). تکرار وب‌هوک، دوبار کلیک، retry کلاینت یا اجرای دوبارهٔ همان تصمیم **ردیف تازه نمی‌سازد**؛ مسابقهٔ هم‌زمان با savepoint جذب می‌شود.
- اعلان فقط **پس از** رسیدن عملیات به وضعیت معتبر در همان تراکنش نوشته می‌شود؛ هیچ فراخوانی شبکهٔ بله داخل تراکنش نیست. شکست ارسال هرگز عملیات را برنمی‌گرداند.
- سه وضعیت جدا: **ثبت‌شده** (ردیف هست)، **ارسال‌شده/در تلاش** (`delivery_attempts` > ۰ و `last_delivery_error`)، **تحویل‌شده** (`delivered_at` فقط با ack ربات). حسابِ بدون هویت بله ⇒ `failed/no_bale_identity` از همان ابتدا؛ این خطای شبکه نیست و به ربات داده نمی‌شود.
- پیوند اعلان (`link`) فقط مسیر نسبی داخل برنامه است (`/event.html?id=…#recording|qa`, `/account.html#orders|certificates|events`)؛ نشانی مطلق، `/api/…`، دانلود، `//`، `..` و بک‌اسلش در سرور رد می‌شود و حساب هم فقط همین الگو را رندر می‌کند. هیچ URL فایل خصوصی در بدنه نیست.
- پنل: «کاربران → گزارش سرور» کارت «صندوق خروجی اعلان‌ها» (`GET /api/admin/notifications`, مجوز `rp_view`) با پنج وضعیت `queued | retrying | delivered | failed | no_bale_identity` و شمارنده‌های سراسری؛ شناسهٔ خام بله برنمی‌گردد.
- ربات: `deliver_pending_notifications` همان ردیف‌ها را می‌خواند؛ اگر `NORA_WEBAPP_URL` در env ربات تنظیم باشد و پیوند نسبی باشد، دکمهٔ «باز کردن در مینی‌اپ» ساخته می‌شود؛ بدون آن فقط متن. **ارسال واقعی بله در این مخزن آزموده نشده** (بدون توکن/اینترنت)؛ وضعیت رسمی: «صف و ساختار اعلان».
- چه چیزهایی عمداً اعلان نمی‌دهند: انتشار زمان‌بندی‌شده در آینده (`publish_at` آینده؛ تا زنده‌شدن واقعی اعلان نمی‌رود — از فاز ۹.۵ زمان‌بند §۱۳ آن را پس از رسیدن زمان یک‌بار اعلان می‌کند)، تمدید دسترسیِ هنوز فعال (ردیف تازه نیست)، تأیید رسید خریدِ فرم‌محور (فقط همان اعلان «دسترسی فعال شد» می‌رود؛ تصمیم ۹.۱)، گواهی بدون تغییر واقعی وضعیت در آینه.
- پایش: تعداد `retrying` و `failed` در همان کارت؛ اگر `no_bale_identity` زیاد شد یعنی کاربران وبی هستند، نه خرابی ربات.

## ۱۰. PDF واقعی گواهی — پیش‌نیاز و روش آزمون (بدون کد در این فاز)

- `bale-bot/nora_bot/certgen.py` برای تبدیل به PDF به `soffice` (LibreOffice) نیاز دارد. در سندباکس این مخزن LibreOffice نیست و قابل نصب نبود؛ بنابراین **هیچ PDF واقعی تولید یا آزموده نشده** و آزمون‌های ربات این مسیر را monkeypatch می‌کنند.
- نصب روی staging (Debian/Ubuntu): `apt-get install -y libreoffice-writer libreoffice-core fonts-dejavu` + فونت فارسی مورد استفادهٔ قالب؛ سپس `soffice --headless --version` باید پاسخ دهد و کاربر سرویس ربات به `$HOME` قابل‌نوشتن برای پروفایل LibreOffice نیاز دارد.
- آزمون پذیرش پیش از ادعا: (۱) با حساب آزمایشی یک گواهی `present` از مرکز گواهی ربات صادر کنید؛ (۲) فایل PDF خروجی را با `pdfinfo` یا باز کردن واقعی بررسی کنید (متن فارسی، راست‌به‌چپ، نام و تاریخ درست)؛ (۳) ابطال همان گواهی و بررسی آینهٔ سرور (`kind=attendance`, `status=revoked`) و اعلان `certificate:*:revoked`؛ (۴) نتیجه را با تاریخ و نسخهٔ LibreOffice در گزارش استقرار ثبت کنید. تا آن زمان وضعیت رسمی: **«آزموده‌نشده»**.

## ۱۱. قاب یوتیوب/آپارات: وضعیت‌های IFrame API و تأیید افشای بیرونی (کامیت ۵ فاز ۹.۵)

- یوتیوب: `src` همان `embed_url` سرور (`youtube-nocookie.com/embed/<id>`) + `enablejsapi=1` (+ `origin` وقتی مبدأ https واقعی است). `event-interaction.js` پیام‌های `postMessage` را **فقط** از `https://www.youtube-nocookie.com` می‌پذیرد و روی قاب می‌نویسد: `data-embed-state ∈ loading|slow|ready|error`، `data-embed-playback ∈ unverified|ready|playing|paused|buffering|ended|error`، `data-embed-api=ready`، `data-embed-error=<کد|unknown>`. کدهای ۱۰۱/۱۵۰/۱۵۳ پیام «صاحب ویدیو نمایش در سایت‌های دیگر را بسته است» می‌دهند؛ پیوند «مشاهده در یوتیوب» فقط با شناسهٔ معتبر ساخته می‌شود. بدون autoplay.
- آپارات: فقط قاب رسمی با hash اعتبارسنجی‌شده؛ چون API وضعیت ندارد، `data-embed-playback` هرگز از `unverified` فراتر نمی‌رود و «پخش شد/تمام شد» ادعا نمی‌شود؛ خطای بارگذاری قاب صادقانه نشان داده می‌شود.
- سرور: انتشار منبع **پولی** (`access=purchased`) با منبع خارجی (`youtube|aparat`) تنها با `acknowledge_external_exposure: true` پذیرفته می‌شود؛ در غیر این صورت `409 {"code":"external_exposure_acknowledgement_required","provider":…}`. تأیید با عامل/زمان در رویداد ممیزی (`external_exposure_acknowledged: true`) ثبت می‌شود. embed خارجی ≠ محتوای محافظت‌شده؛ DRM نیست.
- CSP: بدون تغییر نسبت به §۸ (`NORA_CSP_FRAME_SRC` خالی، `NORA_CSP_REPORT_ONLY=1`). پخش واقعی همچنان **آزموده‌نشده** (بدون اینترنت)؛ دستور آزمون staging همان §۸ است و باید هر سه حالت `ready/playing/error` را در کنسول با `data-embed-*` ببینید.

## ۱۲. PDF واقعی گواهی — ابزار آزمون تکرارپذیر (کامیت ۶ فاز ۹.۵)

- `bale-bot/tools/certificate-pdf-check.py [--json] [--keep]`: مسیر واقعی مرکز گواهی ربات (صدور → تحویل → تکرار → ابطال → بازگردانی) را روی پایگاه آزمایشی موقت اجرا می‌کند و ۱۷ بررسی انجام می‌دهد (PDF معتبر، صفحه‌بندی، متن فارسی RTL در موتور office، تکرار بدون صدور دوباره، همگام‌سازی آینهٔ ابطال/بازگردانی، بدون ارسال به دارنده هنگام تغییر نوع). کد خروج: `0` = همهٔ بررسی‌ها با موتور LibreOffice گذشت؛ `2` = `STAGING_REQUIRED` (LibreOffice نیست؛ رندر داخلی تصویر-تنها، بدون لایهٔ متن و بدون شکستن خط — هرگز «PDF اداری» تلقی نشود)؛ `1` = شکست واقعی.
- `nora_bot/tests/test_certificate_pdf_real_engine.py` همان ابزار را داخل pytest اجرا می‌کند (محلی: ۵ گذر / ۱ skip برای بررسی لایهٔ متن).
- روی staging: `apt-get install -y libreoffice-writer fonts-dejavu` + فونت فارسی قالب، سپس `soffice --headless --version` و اجرای ابزار با کاربر سرویس ربات؛ `pdftotext` (poppler-utils) اختیاری برای بررسی لایهٔ متن. نتیجه (JSON + نسخهٔ LibreOffice) را در گزارش استقرار ثبت کنید. وضعیت رسمی تا آن زمان: **«نیازمند staging»**.

## ۱۳. زمان‌بند انتشار و اعلان محتوا (کامیت‌های ۷ و ۸ فاز ۹.۵)

- منطق: زمان‌بندی فقط روی `event_resources.publish_at` است (جلسه‌ها زمان‌بندی ندارند). **دیده‌شدن محتوا به زمان‌بند وابسته نیست**: صفحهٔ رویداد/کتابخانه در هر درخواست با ساعت سرور `publish_at <= now` را بررسی می‌کند؛ محتوای آینده هرگز عمومی نمی‌شود. زمان‌بند فقط **اعلان** می‌دهد.
- `python -m backend.scheduled_publish --once [--json]` (env: فقط `NORA_DATABASE_URL`): منابع `published` با `publish_at` رسیده و `announced_at = NULL` را می‌گیرد، به دارندگان دسترسی فعال (ردیف `recording_access`) و — اگر محصول `attendee_access` دارد — به حاضرانِ چک‌این‌شده (دسترسی مشتق، بدون ردیف) یک اعلان `recording_content` می‌فرستد، `announced_at` را در همان تراکنش می‌نویسد و نشانگر `scheduled_publish` را ثبت می‌کند. تکرارناپذیری دو لایه دارد: `announced_at` + کلید `recording_content:resource:<id>:<account>`؛ اجرای دوباره، راه‌اندازی مجدد یا اجرای دستی هم‌زمان با تایمر ردیف دوم نمی‌سازد. خروج `0`/`1`.
- systemd: `deployment/nora-scheduled-publish.service` (oneshot، همان `EnvironmentFile` وب) + `deployment/nora-scheduled-publish.timer` (پیش‌فرض ۵ دقیقه، `Persistent=true`؛ تصمیم مالک: ۱ تا ۱۵ دقیقه). دقت اعلان = بازهٔ تایمر. نصب: `systemctl enable --now nora-scheduled-publish.timer`؛ بررسی: `journalctl -u nora-scheduled-publish -n 20`.
- پنل («کاربران → گزارش سرور → زمان‌بند انتشار و اعلان محتوا»): `GET /api/admin/scheduled-publish` (`rp_view`) آخرین اجرا (زمان، عامل `cli`/`owner:…`/`account:…`، شمارش‌ها) و `pending {future, due_unannounced}` را نشان می‌دهد؛ `due_unannounced > 0` یعنی تایمر اجرا نشده (وضعیت `stalled`). «اجرای دستی یک نوبت» = `POST /api/admin/scheduled-publish/run` (`ev_publish`، ممیزی `scheduled_publish.run`). انتشار آنیِ منبع از پنل همان مسیر اعلان را فوراً طی می‌کند و `announced_at` را می‌نویسد؛ برگشت به پیش‌نویس آن را پاک می‌کند تا انتشار دوباره، اعلان دوباره داشته باشد (کلید dedupe جلوی تکرار همان منبع برای همان حساب را می‌گیرد).
- تلاش دوبارهٔ اعلان ناموفق: `POST /api/admin/notifications/{id}/retry` (`ev_publish`) فقط ردیف `failed` با هویت بله را به `pending` برمی‌گرداند (همان ردیف؛ `attempts=0`)؛ `409 already_delivered | notification_not_failed | no_bale_identity`؛ ممیزی `notification.retry`. در پنل دکمه فقط روی همان ردیف‌ها دیده می‌شود و «تحویل» ادعا نمی‌شود.
- آزموده‌شده: pytest (زمان‌بندی/اعلان یک‌بار/حاضران/retry)، jsdom پنل، مرورگر واقعی روی preview با DB آزمایشی (`reports/evidence/phase9.5/browser`). **آزموده‌نشده:** تایمر systemd روی سرور واقعی و تحویل واقعی بله.

## ۱۴. متغیرهای محیطی این فاز و بازگشت

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `NORA_PRIVATE_STORAGE_DIR` | خالی (= inline تا ۸ MiB) | ریشهٔ ذخیره‌سازی خصوصی خارج از وب‌روت |
| `NORA_PRIVATE_STORAGE_MAX_MIB` | `512` | سقف هر فایل؛ سقف پراکسی Caddy باید ≥ همین باشد |
| `NORA_CSP_FRAME_SRC` / `NORA_CSP_REPORT_ONLY` | خالی / `1` | §۸ و §۱۱ |
| `NORA_DATABASE_URL` | — | تنها متغیر لازم برای `backend.scheduled_publish` |

بازگشت: غیرفعال‌کردن تایمر (`systemctl disable --now nora-scheduled-publish.timer`) هیچ داده‌ای را تغییر نمی‌دهد (محتوا با ساعت سرور دیده می‌شود، فقط اعلان خودکار قطع می‌شود؛ اجرای دستی از پنل باقی است). مهاجرت `0036_upload_sessions` (`upload_sessions`, `system_markers`, `event_resources.announced_at`) با `alembic downgrade 0035_notification_dedupe` برمی‌گردد؛ قبل از آن نشست‌های باز آپلود لغو شوند. هیچ مهاجرتی روی تولید اجرا نشده است.
