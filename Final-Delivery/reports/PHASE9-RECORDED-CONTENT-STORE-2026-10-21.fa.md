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

## ب) نتیجهٔ پیاده‌سازی

*(پس از پایان پیاده‌سازی تکمیل می‌شود.)*
