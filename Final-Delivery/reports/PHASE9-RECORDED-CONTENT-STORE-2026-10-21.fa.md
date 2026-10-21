# فاز ۹ — فروش محتوای ضبط‌شده، آرشیو کارگاه‌ها و تکمیل تجربهٔ رویداد

- تاریخ: ۲۰۲۶‑۱۰‑۲۱ (۳۰ مهر ۱۴۰۵)
- شاخه: `arena/840de336-strix` — نقطهٔ شروع: `95eec40` (HEAD فاز ۸ روی GitHub؛ PR شمارهٔ ۱ باز است و باز می‌ماند).
- **رخداد محیط:** در میانهٔ این فاز، سندباکس از نو ساخته شد و پنج کامیت محلیِ هنوز‑push‑نشدهٔ فاز ۹ (طبق قاعدهٔ قبلی «push فقط در پایان») از بین رفت. به تصمیم مالک، فاز ۹ از `95eec40` بازسازی می‌شود و **هر کامیت بلافاصله push و SHA راه‌دور بررسی می‌شود**. هیچ کامیتی از تاریخچهٔ GitHub گم یا بازنویسی نشده است.
- دامنه: تکمیل همین پروژهٔ Nora UI روی همان منبع حقیقت رویداد/ثبت‌نام/حضور/پرداخت؛ بدون پروژه، پنل، درگاه یا سیستم رویداد موازی.
- قاعدهٔ ثابت: «وجود دکمه یا کد ≠ کارکرد». هر ردیف ماتریس با خواندن کد واقعی در `95eec40` (`backend/app.py`, `models.py`, `event_interaction.py`, `bale_payments.py`, `roles.py`, `event-page.js`, `event-interaction.js`, `events-page.js`, `admin.js`, `account.js`) بررسی شده است.

> این سند در دو مرحله نوشته می‌شود: **بخش الف (ممیزی و ماتریس «قبل»)** پیش از هر تغییر کد، در کامیت نخست این فاز؛
> **بخش ب (نتیجهٔ «بعد»، فایل‌ها، APIها، آزمون‌ها، شواهد مرورگر)** پس از پایان پیاده‌سازی.

---

## الف) ممیزی اجباری پیش از کدنویسی

### الف‑۱) سه مفهوم جدا که نباید با هم قاطی شوند

| مفهوم | منبع حقیقت فعلی | چه چیزی را ثابت می‌کند | چه چیزی را ثابت **نمی‌کند** |
|---|---|---|---|
| رویداد + ثبت‌نام + حضور | `site_content.events[]` (شناسهٔ `ev-…`) + `forms.event_id` + `form_responses` (`accepted`, `ticket_checked_in_at`) + `_response_payment_approved()` | کاربر در رویداد ثبت‌نام کرده / حضور داشته | هیچ حقی روی محتوای ضبط‌شده (مگر مالک صریحاً «دسترسی شرکت‌کنندگان» را روشن کند) |
| محتوای ضبط‌شدهٔ وابسته به همان رویداد | **وجود ندارد** (باید ساخته شود: یک محصول به ازای هر رویداد، جلسه‌ها، فایل‌ها) | رویداد برگزارشده‌ای محصولی با قیمت/شرایط دارد | این‌که کسی آن را خریده |
| دسترسی خریداری‌شده/دریافت‌شده به ازای هر حساب | **وجود ندارد** (باید ساخته شود: سفارش + حق دسترسی) | این حساب، به این محصول، تا این تاریخ دسترسی دارد و منبع آن چیست | ثبت‌نام، حضور یا گواهی |

نتیجهٔ ممیزی: «خرید دسترسی» باید **رکورد جدا با منبع، تاریخ انقضا و وضعیت** باشد و هرگز به‌صورت ردیف `form_responses` یا برچسب روی رویداد شبیه‌سازی نشود.

### الف‑۲) زیرساخت موجود که این فاز روی آن سوار می‌شود (و چرا جدول‌های تازه لازم است)

| حوزه | وضعیت واقعی در `95eec40` | تصمیم فاز ۹ |
|---|---|---|
| پرداخت فرم | `form_payments` (`form_id`/`draft_id` **NOT NULL**، FK به فرم و پیش‌نویس؛ `method ∈ card_transfer/bale_wallet`؛ ۹ وضعیت؛ یکتایی `invoice_payload/idempotency_key/transaction_id/provider_charge_id`)؛ نهایی‌سازی بلهٔ آن **ردیف `form_responses` می‌سازد** (`finalize_bale_payment`)؛ فیش کارت‌به‌کارت از طریق `form_receipt_uploads` + `admin_tasks` (کارتابل) و نیازمند ادعای بله. | استفادهٔ مستقیم از `form_payments` برای سفارش محتوا ممکن نیست (ستون‌های اجباری فرم/پیش‌نویس و نهایی‌سازی که ثبت‌نام می‌سازد). **جدول جدای `recording_orders`** با همان الگوی وضعیت‌ها، همان یکتایی‌ها، همان سرویس بله (`bale_payments.call_bale_payment_api`, `validated_invoice_url`) و همان وبهوک. دلیل: جلوگیری از خلط «خرید محتوا» با «ثبت‌نام». |
| سرویس بله | `bale_payments.py`: `createInvoiceLink`, `answerPreCheckoutQuery`, `inquireTransaction`, `getWebhookInfo/setWebhook` (fail‑closed، فقط `tapi.bale.ai`، بدون redirect). وبهوک `POST /api/payments/bale/webhook/{token}` (توکن مشتق HMAC) فقط `nora_…` payload فرم‌ها را می‌شناسد؛ اعطا فقط پس از `inquireTransaction` با وضعیت `paid` و تطبیق مبلغ/ارز/پرداخت‌کننده. | **همان وبهوک** با شاخهٔ تازه برای payload با پیشوند `norac_` (محتوا)؛ همان اصل: اعطای دسترسی فقط پس از استعلام تأییدشده، تکرار تراکنش idempotent، عدم تطبیق → `needs_review`. شبکهٔ خروجی به بله در این محیط نیست → پرداخت واقعی بله «**آزموده‌نشده**» می‌ماند (فقط با سرویس ساختگی در آزمون). |
| کارت‌به‌کارت | مقصد کارت به ازای هر فرم در `settings.paymentCard`؛ فیش ≤ ۸MB فقط تصویر/PDF؛ تأیید دستی با مجوز `receipt_approve`. | کارت مقصد به ازای هر محصول (`payment_card` JSON، هرگز عمومی نمی‌شود)؛ فیش روی خود سفارش؛ **فیش به‌تنهایی هرگز نهایی نمی‌کند**؛ تأیید/رد با `receipt_approve` + دلیل + ممیزی. |
| فایل‌های رویداد | `event_resources` (فاز ۸): بایت‌ها در DB، `access ∈ public/registered/attended/staff`، دانلود فقط از `GET /api/public/events/{id}/resources/{rid}/download` با تصمیم سرور، ۸MB، نوع‌های مجاز: PDF/تصویر/Office/ZIP/MP3/TXT. **MP4 مجاز نیست؛ Range/پخش درون‌صفحه نیست؛ سطح «خریداری‌شده» نیست.** | گسترش همان جدول: `access='purchased'`، `session_id` (پیوند به جلسه)، `delivery ∈ download/view`؛ افزودن `video/mp4` به نوع‌های مجاز با همان سقف ۸MB (واقع‌بینانه: کلیپ‌های کوتاه/پیش‌نمایش؛ ویدئوی کامل کارگاه نیازمند ذخیره‌سازی بیرونی است — **صادقانه در گزارش و پنل**). پاسخ `Range` برای پخش، `inline` برای تحویل «مشاهده». بدون هیچ ادعای DRM. |
| دسترسی حساب | `account_sessions` + `AccountIdentity`؛ هویت بلهٔ تأییدشده از `platform_identities` (`verified_bale_ids_for_account`). | خریدار = حساب نشست؛ پرداخت بله فقط اگر هویت بلهٔ تأییدشده دارد. |
| نقش‌ها | `roles.py`: مدیر = `ev_create, ev_publish, …, receipt_approve`؛ مالک‌فقط = `finance` و …؛ `require_any_permission_write()` = مجوز + same‑origin + CSRF. | هیچ مجوز تازه‌ای: ویرایش محصول/جلسه `ev_create`؛ انتشار/توقف/اعطا/لغو `ev_publish`؛ تأیید/رد فیش `receipt_approve`؛ بازپرداخت `finance` (مالک). |
| اعلان‌ها | `user_notifications` outbox؛ `queued ≠ delivered`؛ حساب بدون بله → `failed/no_bale_identity`. | یک اعلان `recording_access` پس از فعال‌شدن دسترسی (idempotent روی سفارش/دسترسی). |
| ممیزی | `admin_audit_events` + `record_audit()`. | همهٔ اقدام‌های مدیریتی با actor + reason. |
| صفحهٔ رویداد | `event-page.js` (عکس عمومی) + `event-interaction.js` (منابع/پرسش/دیدگاه از `/interaction`). رویداد برگزارشده: ستون «اطلاعات آرشیو» بدون CTA. | همان صفحه: بخش «محتوای ضبط‌شده» + CTA یگانهٔ سروری در همان ستون؛ هیچ صفحهٔ محصول جداگانه‌ای. |
| فهرست رویدادها | `events-page.js`: صافی `all/upcoming/past`، نوع/شیوه، جست‌وجو شامل مدرس. | افزودن «ضبط‌شده» و صافی رایگان/قابل خرید از خلاصهٔ سروری؛ کارت‌ها بدون هیچ شمار خریدار/تخفیف. |
| حساب | `account.js`: ثبت‌نام‌ها، پرداخت‌های ثبت‌نام، اعلان‌ها، فایل‌ها. | «محتوای من» و «سفارش‌های محتوا» از دو API تازه؛ «ادامهٔ مشاهده» فقط اگر دادهٔ پیشرفت واقعی وجود داشته باشد (وجود ندارد → ساخته نمی‌شود). |
| پنل | `admin.js` بخش رویدادها با ابزار منابع/پرسش/دیدگاه (فاز ۸)؛ کارتابل فیش فرم‌ها. | همان بخش رویدادها: زبانهٔ «محتوای ضبط‌شده»؛ فهرست سفارش‌ها/دسترسی‌ها در همان ماژول. |

### الف‑۳) ماتریس تطبیق «قبل»

دسته‌ها: **A** موجود و سالم · **B** موجود ولی ناقص · **C** صرفاً ظاهری/آزمایش‌نشده · **D** کاملاً غایب

| # | قابلیت | وضعیت | منبع/مدل فعلی | شکاف واقعی | تغییر لازم | آزمون پذیرش |
|---|---|---|---|---|---|---|
| ۱ | رویداد برگزارشده در آرشیو | **A** | `events[].past`, `registration.state=ended` | — | — | رگرسیون فاز ۷ |
| ۲ | محصول ضبط‌شدهٔ وابسته به رویداد (وضعیت draft/ready/published/sales_paused/archived) | **D** | — | هیچ مدلی نیست | `event_recordings` (event_id یکتا) | رویداد آینده هرگز published نمی‌شود؛ بدون جلسهٔ منتشرشده هرگز published نمی‌شود |
| ۳ | جلسه‌ها (عنوان/ترتیب/مدت/پیش‌نمایش/وضعیت) | **D** | — | — | `recording_sessions` | حذف جلسهٔ دارای فایل → 409 |
| ۴ | فایل جلسه با سطح «خریداری‌شده» و تحویل دانلود/مشاهده | **B** | `event_resources` بدون `purchased/session_id/delivery/mp4` | دسترسی خرید و پخش وجود ندارد | ALTER همان جدول | مهمان 401، عضو بی‌دسترسی 403 `purchase_required` + ممیزی، دارندهٔ دسترسی 200؛ `view` → inline + Range 206/416 |
| ۵ | سفارش خرید (کارت‌به‌کارت/بله) با مبلغ سروری، idempotent | **D** | `form_payments` غیرقابل‌استفاده (الف‑۲) | — | `recording_orders` | دو POST با همان کلید → همان سفارش؛ مبلغ از سرور؛ تغییر قیمت با سفارش باز → 409 |
| ۶ | فیش کارت‌به‌کارت و تصمیم انسانی | **B** | الگوی فرم‌ها | برای محصول نیست | `PUT …/receipt` + `POST …/decision` | فیش → `receipt_submitted` و **بدون دسترسی**؛ تأیید → `paid_manual` + دسترسی؛ تکرار تصمیم → 409 |
| ۷ | پرداخت کیف پول بله با وبهوک تأییدشده | **B** | وبهوک فقط فرم‌ها | شاخهٔ محتوا نیست | پیشوند `norac_` در همان وبهوک | pre_checkout با مبلغ غلط رد؛ موفقیت بدون استعلام `paid` → بدون دسترسی؛ تکرار → یک دسترسی |
| ۸ | حق دسترسی (purchase/free/granted؛ active/expired/revoked؛ انقضا) | **D** | — | — | `recording_access` (یکتا recording+account) | انقضا → `expired`؛ بازپرداخت → `revoked`؛ لغو با دلیل |
| ۹ | دریافت رایگان بدون تراکنش ساختگی | **D** | — | — | `POST /api/account/recordings/{id}/claim` | محصول پولی → 409؛ هیچ ردیف سفارش ساخته نمی‌شود |
| ۱۰ | بازپرداخت واقعی | **D** | — | — | `POST …/refund {reference, reason}` با `finance` | وضعیت `refunded` + دسترسی `revoked` در یک تراکنش؛ مدیر بدون `finance` → 403 |
| ۱۱ | اعطای دستی/لغو دسترسی با دلیل | **D** | — | — | `…/recording/access` | بدون دلیل → 422؛ ممیزی با actor |
| ۱۲ | صفحهٔ محصول روی همان صفحهٔ رویداد با CTA یگانهٔ سروری | **D** | `event-page.js` | — | `viewer.cta.kind` از سرور | مهمان → ورود با بازگشت؛ دارنده → «مشاهدهٔ جلسات»؛ متوقف → بدون دکمه |
| ۱۳ | رویداد برگزارشده بدون محصول منتشرشده | **A→باید بماند** | ستون «اطلاعات آرشیو» | — | هیچ CTA خرید | کارت/صفحه بدون دکمهٔ خرید |
| ۱۴ | کارت‌های آرشیو با برچسب ضبط‌شده/قیمت/جلسه‌ها | **D** | `events-page.js` | — | خلاصهٔ `event.recording` در عکس عمومی (فقط published/sales_paused) | مدت فقط اگر همهٔ جلسه‌ها مدت دارند |
| ۱۵ | بنر محصول ضبط‌شده → بخش فروش، بدون شمارش ثبت‌نام | **B** | `_public_banner_rows` → `event.html?id=` | — | href `#recording` + حذف شمارش | آزمون سروری |
| ۱۶ | «محتوای من» و «سفارش‌های محتوا» در حساب | **D** | — | — | `GET /api/account/recordings`, `GET /api/account/recording-orders` | حساب دیگر → 404 |
| ۱۷ | پرسش‌وپاسخ/دیدگاه روی محصول | **A** (فاز ۸) | همان رویداد | نشان «خریدار تأییدشده» نیست | `event_reviews.badge`؛ واجد شرایط = حضور **یا** دسترسی فعال خریداری‌شده | دارندهٔ دسترسی بدون حضور → نشان «خریدار تأییدشده» |
| ۱۸ | پنل: مدیریت محصول/جلسه/فایل/قیمت/وضعیت در بخش رویدادها | **D** | `admin.js` | — | زبانهٔ «محتوای ضبط‌شده» روی `NORA_SERVER_API` | آزمون jsdom پنل |
| ۱۹ | پنل: صف سفارش‌ها (بررسی فیش/تصمیم/بازپرداخت/تاریخچه) | **D** | — | — | `GET /api/admin/recording-orders…` | مدیر بدون `receipt_approve` فیش را نمی‌بیند |
| ۲۰ | داشبورد فروش فقط از دادهٔ واقعی | **D** | — | — | `GET /api/admin/recordings/summary` | شمارش‌ها = ردیف‌های DB |
| ۲۱ | پیشرفت مشاهده («ادامهٔ مشاهده») | **D** | — | هیچ دادهٔ پیشرفتی | **ساخته نمی‌شود** (بدون دادهٔ واقعی دکمه‌ای نمایش داده نمی‌شود) | — |
| ۲۲ | ذخیره‌سازی/استریم ویدئوی بلند، CDN، DRM | **D** | — | زیرساخت نیست | **ساخته نمی‌شود**؛ در پنل و گزارش «نیازمند سرویس» | — |

### الف‑۴) مدل دادهٔ حداقلی (مهاجرت `0032_recorded_content`)

- `event_recordings`: `id`, `event_id` (یکتا), `status` (`draft/ready/published/sales_paused/archived`), `title`, `summary`, `outcomes`, `audience`, `access_terms`, `refund_policy`, `faq` (JSON), `price` (۰..۲e9 ریال), `currency`, `access_days` (NULL = دائمی), `attendee_access`, `download_default`, `bale_enabled`, `payment_card` (JSON؛ هرگز عمومی نمی‌شود), `cover_url`, `published_at`, `status_reason`, `version`, actor/زمان‌ها.
- `recording_sessions`: `id`, `recording_id`, `title`, `description`, `sort_order`, `duration_minutes`, `status` (`draft/published/hidden`), `preview`.
- `recording_orders`: `id`, `recording_id`, `account_id`, `method`, `status` (`pending/awaiting_receipt/receipt_submitted/paid/paid_manual/needs_review/rejected/cancelled/expired/refunded`), `amount`, `currency`, `idempotency_key` (یکتا), `invoice_payload/invoice_url/transaction_id/provider_charge_id` (یکتا), `payer_bale_user_id`, `expires_at`, فیش (`receipt_*` ≤ ۸MB), تصمیم (`decided_*`, `decision_reason`, `review_note`), `refund_reference/refunded_at`.
- `recording_access`: `id`, `recording_id`, `account_id` (یکتا با هم), `source` (`purchase/free/granted`), `status` (`active/expired/revoked`), `order_id`, `expires_at`, `granted_by_*`, `reason`, `revoked_*`.
- ALTER: `event_resources.session_id`, `event_resources.delivery` (`download/view`), `access` + `purchased`؛ `event_questions.session_id`؛ `event_reviews.badge`.
- همهٔ تغییرات افزایشی و برگشت‌پذیر؛ `downgrade` ردیف‌های `purchased` را به `staff` برمی‌گرداند تا قید قدیمی برقرار بماند. آزمون روی SQLite و PostgreSQL.

### الف‑۵) ترتیب کامیت‌ها (هر کدام مستقل، push بلافاصله)

۱) همین گزارش ممیزی → ۲) مدل + مهاجرت + آزمون مهاجرت → ۳) `recordings.py` + APIهای فروش/دسترسی/وبهوک + آزمون API → ۴) پنل (محصول/جلسه/سفارش‌ها) → ۵) آرشیو/فروشگاه/صفحهٔ محصول/CTA → ۶) حساب («محتوای من»، سفارش‌ها) → ۷) پرسش/دیدگاه (نشان خریدار) → ۸) ابزار فروش (خلاصه/جست‌وجو/خروجی) → ۹) طراحی/امنیت/رگرسیون کامل (SQLite+PG+Node+مرورگر) → ۱۰) شواهد و بخش ب.

---

> **پی‌نوشت (فاز ۹.۱، ۲۰۲۶‑۱۰‑۲۲):** تصمیم «مسیر سفارش مستقل از فرم‌ساز» این فاز در `PHASE9.1-FORM-ALIGNED-STORE-CERTIFICATES-VIDEO-2026-10-22.fa.md` ممیزی و اصلاح می‌شود: منبع قیمت/روش/کارت مقصد به فرم خرید (`forms.purpose=recording_access`) برمی‌گردد و `recording_orders` فقط دفتر داخلی پیوندخورده به پاسخ/پرداخت فرم می‌ماند.

## ب) نتیجهٔ پیاده‌سازی

- **آخرین SHA کد (این گزارش روی آن نوشته شده):** `96b9b5e` روی `arena/840de336-strix` (origin == local، بررسی‌شده با `git rev-parse`). کامیت این گزارش پس از آن می‌آید. PR شمارهٔ ۱ همچنان **باز** است و merge نشده؛ هیچ deploy، مهاجرت تولید، انتشار یا تغییر دادهٔ واقعی انجام نشده است.
- **رخدادهای محیط در این فاز (صادقانه):** ۱) سندباکس دو بار از نو ساخته شد؛ بار اول پنج کامیت push‑نشده از بین رفت و فاز از `95eec40` بازسازی شد؛ بار دوم پس از کامیت ۷، فقط محیط (venv/node/پیش‌نمایش) بازسازی شد و تاریخچهٔ GitHub دست‌نخورده ماند (بازیابی با `git merge --ff-only`، بدون reset). ۲) دانلود مرورگر Playwright از CDN در این سندباکس مسدود است؛ شواهد مرورگر با `@sparticuz/chromium` از طریق همان `tools/browser-launch.cjs` (`NORA_QA_BROWSER=sparticuz`) گرفته شد. ۳) محیط بات و Node پس از بازسازی دو وابستگی (`sqlalchemy` برای `test_legacy_data_audit`، `jsqr` برای `qr.test.mjs`) کم داشت؛ هر دو نصب و سوئیت‌ها **کامل دوباره** اجرا شدند؛ اعداد زیر از اجرای نهایی روی `96b9b5e` است.

### ب‑۱) ماتریس «بعد» (همان ردیف‌های الف‑۳)

| # | قابلیت | وضعیت بعد | کجا / چطور اثبات شد |
|---|---|---|---|
| ۲ | محصول ضبط‌شده با وضعیت‌های `draft/ready/published/sales_paused/archived` | **A** | `backend/recordings.py` (گذارها + `publish_blockers`)، `test_recordings_api.py::test_free_claim_manual_grant_and_draft_visibility…`؛ پنل: `admin-recordings.test.mjs`؛ تصویر `d-11-owner-product.png` |
| ۳ | جلسه‌ها (عنوان/ترتیب/مدت/پیش‌نمایش/وضعیت) | **A** | CRUD با `ev_create`؛ حذف جلسهٔ دارای فایل ۴۰۹؛ آزمون API + jsdom |
| ۴ | فایل جلسه با سطح `purchased` و تحویل `download/view` | **A** | دانلود: مهمان ۴۰۱، بی‌دسترسی ۴۰۳ `purchase_required` + ممیزی، دارنده ۲۰۰/۲۰۶؛ همان نقطهٔ فاز ۸؛ بررسی مرورگری «guest/pending direct URL» و «buyer stream» (۲۰۶ با Range) |
| ۵ | سفارش idempotent با مبلغ سروری | **A** | `recording_orders` + `Idempotency-Key`؛ تغییر قیمت با سفارش باز ۴۰۹ |
| ۶ | رسید کارت‌به‌کارت + تصمیم انسانی | **A** | رسید → `receipt_submitted` **بدون دسترسی** (تصویر `m-05/d-05-pending-order`)، تأیید با `receipt_approve` و دلیل → `paid_manual` + دسترسی؛ رد → اعلان با دلیل (`test_rejected_card_orders_notify…`) |
| ۷ | کیف پول بله با وب‌هوک تأییدشده | **شبیه‌سازی‌شده** | `test_wallet_orders_grant_access_only_from_the_verified_webhook…`: پرداخت موفق بدون `inquireTransaction`=paid → `needs_review` و بدون دسترسی؛ تکرار → یک دسترسی. **با سرویس واقعی بله آزموده نشده** (دسترسی خروجی نیست). |
| ۸ | حق دسترسی با منبع/وضعیت/انقضا | **A** (انقضا: محاسبه‌شده هنگام خواندن؛ **زمان‌بند انقضا ساخته نشده**) | `recording_access` یکتا؛ `access_state()`؛ بازپرداخت → `revoked` |
| ۹ | دریافت رایگان بدون تراکنش ساختگی | **A** | `claim` هیچ ردیف سفارش نمی‌سازد؛ تصویر `*-09-free-holder` |
| ۱۰ | بازپرداخت واقعی | **A (دستی)** | فقط `finance` (مالک)، شمارهٔ پیگیری اجباری، `refunded` + `revoked` اتمی؛ مدیر دکمه ندارد و API ۴۰۳ می‌دهد. بازپرداخت خودکار درگاه **ساخته نشده** (سرویسی نیست). |
| ۱۱ | اعطا/لغو دستی با دلیل | **A** | ۴۲۲ بدون دلیل؛ actor در ممیزی؛ پنل «دسترسی‌ها» |
| ۱۲ | صفحهٔ محصول روی همان `event.html` با CTA یگانهٔ سروری | **A** | `viewer.cta.kind`؛ تصاویر `*-02-event-guest` (ورود)، `*-05` (سفارش باز)، `*-07-buyer-view` (مشاهده)؛ `event-recording.test.mjs` ۵۷ بررسی |
| ۱۳ | برگزارشده بدون محصول منتشرشده ≠ قابل خرید | **A** | تصویر `*-03-held-no-product`: بدون هیچ دکمهٔ خرید؛ ثبت‌نام «پایان‌یافته» |
| ۱۴ | کارت‌های آرشیو با برچسب/قیمت/جلسه‌ها | **A** | `#recorded` در `events.html` (تصویر `*-01-events-recorded`)؛ پیش‌نویس‌ها در فهرست عمومی نیستند (بررسی مرورگری) |
| ۱۵ | بنر محصول ضبط‌شده → بخش فروش | **A** | `href` به `event.html?id=…#recording`، بدون شمارش معکوس |
| ۱۶ | «محتوای من» و «سفارش‌ها و پرداخت‌ها» | **A** | تصاویر `*-08-account-library`, `*-06-account-orders`؛ «ادامهٔ مشاهده» نمایش داده **نمی‌شود** (`progress: null`) |
| ۱۷ | نشان «خریدار تأییدشده» سروری | **A** | `event_reviews.badge` از سرور؛ بررسی مرورگری «buyer badge» روی دیدگاه منتشرشده؛ پرسش با `session_id` اختیاری |
| ۱۸ | پنل: محصول/جلسه/فایل/قیمت/وضعیت | **A** | زبانهٔ «ضبط‌شده و فروش» داخل همان ابزار رویداد؛ تصویر `d-11-owner-product` |
| ۱۹ | پنل: صف سفارش‌ها | **A** | کارتابل با فیلتر وضعیت/رویداد/جست‌وجو، تصمیم با دلیل، تاریخچه، CSV فقط مالک؛ تصویر `*-10-manager-orders` (مدیر بدون بازپرداخت) |
| ۲۰ | داشبورد فروش از دادهٔ واقعی | **A** | `GET /api/admin/recordings/summary` = شمارش ردیف‌ها؛ اشکال شمارنده‌های صفر در کادر محصول در این فاز پیدا و رفع شد (ب‑۴) |
| ۲۱ | «ادامهٔ مشاهده» | **عمداً ساخته نشد** | بدون دادهٔ پیشرفت واقعی، دکمه‌ای نمایش داده نمی‌شود |
| ۲۲ | استریم/CDN/DRM/ویدئوی بلند | **نیازمند سرویس** | پنل و صفحه صریحاً می‌گویند: فایل ≤ ۸MB در حافظهٔ خصوصی سرور (بایت‌ها در DB)، پخش با Range از نقطهٔ مجوزدار؛ هیچ ادعای حفاظت از کپی |

### ب‑۲) مسیر خرید (آن‌طور که واقعاً اجرا می‌شود)

۱) مهمان صفحهٔ محصول را می‌بیند؛ CTA «ورود برای خرید دسترسی» با بازگشت به `event.html?id=…#recording`. ۲) عضو واردشده «خرید دسترسی» می‌زند → `POST /api/account/recordings/{id}/orders {method}`؛ مبلغ/ارز را سرور از محصول می‌خواند؛ کلید idempotency از مرورگر فقط برای جلوگیری از سفارش تکراری. ۳) کارت‌به‌کارت: سفارش `awaiting_receipt`، کارت مقصد از تنظیم محصول؛ کاربر رسید می‌فرستد → `receipt_submitted` (هنوز **هیچ دسترسی**). ۴) مدیر/مالک با `receipt_approve` در کارتابل تصمیم می‌گیرد (دلیل اجباری) → `paid_manual` + ردیف `recording_access` + اعلان `recording_access` در صندوق خروجی (ثبت ≠ تحویل). ۵) کیف پول بله: فاکتور سروری؛ دسترسی فقط از وب‌هوک با `inquireTransaction` موفق؛ ناهمخوانی مبلغ/کاربر → `needs_review`. ۶) کاربر در «محتوای من» دسترسی و مهلت را می‌بیند؛ پخش/دانلود هر فایل با بررسی سروری همان لحظه. ۷) بازپرداخت فقط مالک با شمارهٔ پیگیری → `refunded` + `revoked`.

### ب‑۳) مجوزها و امنیت فایل

- `ev_create`: محصول/جلسه/فایل؛ `ev_publish`: وضعیت، اعطا/لغو؛ `receipt_approve`: دیدن رسید و تصمیم؛ `finance` (فقط مالک): بازپرداخت و CSV. همه سمت سرور؛ پنهان‌کردن دکمه کنترل دسترسی نیست و برای هر مسیر آزمون ۴۰۳ وجود دارد.
- فایل‌ها: allowlist نوع (ویدئو فقط `video/mp4`، تصویر، PDF)، حجم ≤ ۸MB، نام کنترل‌شده، بایت‌ها در DB خصوصی؛ هیچ URL عمومی/دائمی؛ هر درخواست دانلود با نشست سرور و دسترسی فعل‌ی سنجیده و تلاش غیرمجاز ممیزی می‌شود؛ `nosniff` + `no-store`؛ رسید ≤ ۸MB با نرخ‌محدودی.
- بدون DRM/حفاظت از کپی؛ این محدودیت در پنل (`data-rec-limits`) و اینجا نوشته شده است.

### ب‑۴) اشکال‌هایی که پیش‌نمایش مرورگری پیدا کرد (و رفع شد در `96b9b5e`)

1. **backend:** اولین `PUT …/recording` با `faq` به `TypeError` می‌خورد (کلید دوبار پاس می‌شد). آزمون‌های واحد این حالت را نمی‌پوشاندند؛ seed پیش‌نمایش آن را آشکار کرد → اصلاح + assert در `test_recordings_api.py`.
2. **صفحهٔ رویداد:** پیوندهای درون‌صفحه‌ای CTA (`#recording-sessions`, `#recording-order`, `#recording`) رویداد `hashchange` می‌ساختند و `ui.js::uiHash` روی صفحه‌های `?id=` ورقهٔ نمایشی قدیمی (با «NaN قلم · NaN خرید» و «بستهٔ کامل») را روی صفحهٔ واقعی باز می‌کرد — دقیقاً همان UI فروش ساختگی که ممنوع است. رفع: پرش با `replaceState` + `scrollIntoView` بدون `hashchange`، آزمون jsdom. کد مشترک `ui.js` دست نخورد.
3. **پنل:** کادر وضعیت محصول کلیدهای شمارنده را با نام‌هایی می‌خواند که سرور هرگز نمی‌فرستد (`open_orders` به‌جای `orders_open` …) و همیشه «۰» نشان می‌داد؛ mock آزمون هم همان کلیدهای اشتباه را داشت. رفع: خواندن کلیدهای واقعی سرور + شمارش جلسات از فهرست واقعی؛ mock آزمون با سرور هم‌راستا و assert «صفر ساختگی ممنوع».
4. **بصری (جدا گزارش می‌شود):** نوار پایین دسکتاپ، عنوان محصول و برچسب «محتوای ضبط‌شده» را به هم چسبانده بود → سه قاعدهٔ CSS محدود به `#ctabar` در `event-interaction.css` (v=4).

### ب‑۵) نتیجهٔ آزمون‌ها (اجرای نهایی روی `96b9b5e`، خروجی واقعی)

| سوئیت | فرمان | نتیجه | کد خروج |
|---|---|---|---|
| backend pytest (SQLite) | `python -m pytest tests -q -p no:cacheprovider` در `nora-ui/backend` | **273 passed, 4 skipped** (skip: `test_migrations_postgres` بدون `NORA_TEST_POSTGRES_URL` — همان آزمون در اجرای PG زیر پاس شد) | 0 |
| backend pytest (PostgreSQL) | `python tools/run-postgres-tests.py` (pgserver موقت) | **277 passed** | 0 |
| mypy | `python -m mypy --config-file backend/mypy.ini backend` | Success: no issues found in 63 source files | 0 |
| bot pytest | `python -m pytest -q -p no:cacheprovider` در `Final-Delivery/bale-bot` | **202 passed, 1 skipped** (اجرای اول پس از بازسازی محیط: ۱ خطای محیطی `sqlalchemy` → نصب → اجرای کامل دوباره) | 0 |
| Node (همهٔ سوئیت‌ها) | `node tools/run-unit-tests.cjs` | **34/34 suites passed** (اجرای اول: `qr.test.mjs` به‌خاطر نبود `jsqr` در محیط بازسازی‌شده FAIL؛ نصب → اجرای کامل دوباره: 34/34) — شامل `admin-recordings`، `event-recording` (57 بررسی)، `account-recordings`، `event-interaction` (32/32)، `events-page` (89)، `admin` | 0 |
| مرورگر (Chromium headless، سرور آزمایشی + DB آزمایشی) | `tools/phase9-browser-evidence.cjs` | **32/32 بررسی** در دو اندازهٔ ۳۹۰×۸۴۴ و ۱۲۸۰×۸۰۰ (`evidence/phase9/browser-checks.txt`) | 0 |

**آزموده‌نشده / غیرقابل آزمون در این محیط:** پرداخت واقعی کیف پول بله و تحویل واقعی پیام بله (فقط شبیه‌سازی وب‌هوک و صندوق خروجی)؛ انقضای خودکار با زمان‌بند (وضعیت هنگام خواندن محاسبه می‌شود)؛ فایل‌های ویدئویی بزرگ (حد ۸MB)؛ مرورگرهای واقعی موبایل/Safari (فقط Chromium headless).

### ب‑۶) شواهد (`Final-Delivery/reports/evidence/phase9/`، فقط دادهٔ مصنوعی، بدون رمز)

پیشوند `m-` = ۳۹۰×۸۴۴، `d-` = ۱۲۸۰×۸۰۰: `01-events-recorded` (آرشیو با صافی «ضبط‌شده»؛ فقط محصول‌های منتشرشده)، `02-event-guest` (CTA ورود، بدون خرید/شمارش معکوس)، `03-held-no-product` (برگزارشده بدون محصول: هیچ دکمهٔ خرید)، `04-upcoming` (ثبت‌نام باز، بدون محصول)، `05-pending-order` (رسید ارسال‌شده، بدون دسترسی)، `06-account-orders` (سفارش محتوا جدا از پرداخت ثبت‌نام)، `07-buyer-view` (پخش‌کننده از نقطهٔ مجوزدار، دانلود فقط برای فایل قابل‌دانلود)، `08-account-library` («محتوای من» با مهلت واقعی، بدون «ادامهٔ مشاهده»)، `09-free-holder` (دسترسی رایگان بدون تراکنش)، `10-manager-orders` (کارتابل مدیر؛ بدون بازپرداخت)، `11-owner-product` (زبانهٔ محصول در ابزار رویداد با شمارنده‌های واقعی). بررسی‌های API داخل همان نشست مرورگر: مهمان ۴۰۱، سفارش باز ۴۰۳ `purchase_required`، خریدار ۲۰۶ با Range.

### ب‑۷) اجرای محلی و پیش‌نمایش (فقط دادهٔ آزمایشی)

1. `NORA_PREVIEW_DIR=/tmp/nora-preview python tools/phase9-preview-seed.py` (از `nora-ui`؛ DB و `preview.env` و فایل محلی `PREVIEW-LOGIN.local.md` را می‌سازد؛ رمزها هرگز چاپ نمی‌شوند).
2. `set -a; . /tmp/nora-preview/preview.env; set +a; python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000` — ورود کارکنان از `/login.html?mode=staff&next=admin.html%23dash`؛ اعضا با هویت بلهٔ آزمایشی (`/api/auth/bale-mini-app` با initData امضاشده با توکن آزمایشی).
3. شواهد: `NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps> node tools/phase9-browser-evidence.cjs <dir>`.
4. پیش‌نمایش سندباکس فقط برای همین جلسه زنده است و آدرس عمومی نیست.

### ب‑۸) نیازهای استقرار (code‑ready ≠ deploy‑ready)

- اجرای مهاجرت `0032_recorded_content` روی staging با پشتیبان و بررسی `downgrade` (آزموده روی SQLite و PostgreSQL در آزمون؛ **روی DB تولید اجرا نشده**).
- پیکربندی کیف پول بله (همان `NORA_FORM_PAYMENT_PROVIDER_TOKEN` موجود که فرم‌ها هم استفاده می‌کنند؛ متغیر تازه‌ای افزوده نشده) اگر فروش با بله می‌خواهید؛ بدون آن سرور ۵۰۳ `payment_method_not_available` می‌دهد و فقط کارت‌به‌کارت فعال است.
- زمان‌بند/کران برای انقضای دسترسی و پاک‌سازی سفارش‌های `expired` (اکنون وضعیت هنگام خواندن محاسبه می‌شود).
- برای ویدئوهای بلند: حافظهٔ شیء/استریم خصوصی — خارج از این فاز و هنوز سرویسی وجود ندارد.

### ب‑۹) فایل‌های تغییریافته (`95eec40..96b9b5e`؛ ۶۴ فایل)

backend: `app.py`, `recordings.py` (جدید), `event_interaction.py`, `models.py`, `migrations/versions/0032_recorded_content.py`, `tests/test_recordings_api.py` (جدید), `tests/test_migrations.py`, `tests/test_migrations_postgres.py`, `tests/test_local_development.py`, `README.fa.md` · front‑end: `event-interaction.js/.css`, `event-page.js`, `events-page.js`, `public-data.js`, `account.js/.css/.html`, `admin.js/.html`, `owner-api.js`, `event.html`, `events.html`, `home.html` و سایر صفحه‌ها (فقط پین نسخهٔ اسکریپت مشترک) · آزمون‌های jsdom: `admin-recordings.test.mjs`, `event-recording.test.mjs`, `account-recordings.test.mjs` (جدید) + به‌روزرسانی `admin/account/event-interaction/events-page/support.test.mjs` · ابزار: `tools/phase9-preview-seed.py`, `tools/phase9-browser-evidence.cjs` · شواهد: `reports/evidence/phase9/`.
