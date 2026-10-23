# یکپارچه‌سازی پروندهٔ رویداد (فرم‌ها، ثبت‌نام، پرداخت، بلیت، حضور) — ۱۴۰۵/۰۸/۰۱

مخزن `erfan0843/strix` · شاخهٔ `arena/840de336-strix` · پایهٔ کار `dac1ee0c8152` (گزارش ساده‌سازی پنل).
همهٔ آزمون‌ها روی پایگاه آزمایشی (`/home/user/nora-preview/nora.db`، حساب‌های مصنوعی) انجام شده؛ هیچ تغییری روی دادهٔ واقعی، بله یا پرداخت واقعی نیست.

## فاز ۱ — نقشهٔ داده و منبع حقیقت (کشف، بدون تغییر کد)

### ۱.۱ جدول‌ها و رابطه‌ها (از `backend/models.py`)

| مفهوم | جدول / ستون | نکتهٔ مالکیت |
| --- | --- | --- |
| رویداد | `site_content.content.events[]` (JSON، `id`، `t`، `status`، `cap`، `price`، `regMode`، `startsAt`…) | یک رکورد `public` نسخه‌دار؛ مالک = `owner_id` |
| فرم | `forms` (`id`، `owner_id`، `title`، `model`، `need`، `purpose`، **`event_id`**، `status`، `version`، `settings` JSON) | **پیوند فرم↔رویداد = `forms.event_id`** (یک فرم ↔ حداکثر یک رویداد) |
| نوع فرم | `model`→`need`: `registration→reg`، `order→reg`، `survey→survey`، `exam/contest→exam`، بقیه→`other` | `purpose='recording_access'` = فرم خرید محصول (هرگز ثبت‌نام/بلیت نیست) |
| پاسخ / ثبت‌نام | `form_responses` (`form_id`، `draft_id`، `status∈{accepted,waitlisted}`، `answers`، `form_snapshot`، `registrant_name/mobile`، `ticket_serial`، `ticket_checked_in_at/by`، `receipt_review_task_id`، همراهان با `added_by_response_id`) | هویت ثبت‌نام‌کننده از `form_response_drafts.account_id` یا `bot_bale_user_id` |
| پرداخت | `form_payments` (`form_id`، `draft_id`، `response_id` یکتا، `method∈{card_transfer,bale_wallet}`، `status∈{pending,paid,paid_review,awaiting_receipt,receipt_submitted,paid_manual,rejected,cancelled,expired}`، `amount`، `transaction_id`) + `form_payment_transactions` (کال‌بک‌ها) | حداکثر یک پرداخت به‌ازای هر پاسخ |
| رسید | `form_receipt_uploads` (محتوای فایل، یکتا به‌ازای پاسخ) و/یا کار `admin_tasks(kind=receipt_review)` با `file_refs` → `private_files` | رسید از بله = کار صندوق؛ رسید وب = ردیف `form_receipt_uploads` |
| بلیت | ستون‌های `ticket_*` روی همان `form_responses` (بدون جدول جدا) | کیوآر = `ftv_<response uuid>` (غیرقابل حدس، بدون دادهٔ شخصی) |
| حضور | `form_responses.ticket_checked_in_at` + ممیزی `attendance.check_in / undo_check_in` | ــ |
| گواهی | `certificates` (`kind`، `event_ref`، `account_id`) | فقط‌خواندنی در پنل |
| فایل‌ها | `event_resources` (فایل/پیوند/ویدیو با سطح دسترسی) | زبانهٔ موجود «فایل‌ها و رسانه‌ها» |
| ممیزی | `admin_audit_events` (`GET /api/owner/audit` فقط مالک) | ــ |

### ۱.۲ منبع حقیقتِ ظرفیت و قیمت (یافتهٔ اصلی)

* **اعمال واقعی** ظرفیت در سرور فقط از `forms.settings.cap` و `forms.settings.wait` انجام می‌شود (`_capacity_is_full` در `app.py` و همهٔ مسیرهای ثبت پاسخ، پرداخت بله و بات). مبلغ واقعی فقط از `forms.settings.fin / groups / coupon` محاسبه می‌شود (`financials.calculate_payment_amount`)؛ روش پرداخت از `enabledPaymentMethods` / `receiptReviewRequired`.
* رکورد رویداد فیلدهای `cap` و `price` هم دارد، اما **هیچ‌جا در سرور اعمال نمی‌شوند**؛ فقط روی کارت و صفحهٔ عمومی چاپ می‌شدند (`events-page.js`، `event-page.js`) و در پنل با برچسب «ظرفیت اعلامی / هزینهٔ نمایشی کارت». یعنی دو مقدار موازی وجود داشت که می‌توانستند با هم نخوانند.
* **تصمیم (طبق مأموریت):** منبع حقیقت = فرم ثبت‌نام اصلیِ رویداد (منتشرشده، `need=reg`، `purpose=registration`؛ همان قاعدهٔ `_content_registration_summary` و اسنپ‌شات عمومی). پروندهٔ رویداد و صفحهٔ عمومی مقدارها را از فرم می‌خوانند با برچسب «تنظیم‌شده در فرم ثبت‌نام». مقدار ذخیره‌شدهٔ رویداد **بازنویسی نمی‌شود**؛ فقط وقتی فرمی وصل نیست به‌عنوان «اعلامی» نمایش داده می‌شود. ویرایش ظرفیت/قیمت = «ویرایش تنظیمات ثبت‌نام» که فرم‌ساز را روی همان فرم با زمینهٔ رویداد باز می‌کند.
* **شمارش مؤثر:** ثبت‌نام = `form_responses.status='accepted'` (پذیرفته) و `waitlisted` جدا؛ رزرو موقت بله (`_active_bale_payment_holds`) فقط در سنجش «تکمیل ظرفیت» حساب می‌شود؛ پرداخت تأییدشده = `paid` (بله) یا `paid_manual` (کارت‌به‌کارت تأییدشده) یا «بدون نیاز به پرداخت» (`_response_payment_approved`). **وضعیت ثبت‌نام ≠ وضعیت پرداخت ≠ حضور.**

### ۱.۳ نقطه‌های پایانی موجود (استفاده‌شده بدون تغییر)

| نیاز | موجود |
| --- | --- |
| فهرست فرم‌ها (برای انتخاب فرم موجود) | `GET /api/forms` (`ev`، `response_count`، `version`) |
| اتصال / قطع اتصال فرم به رویداد | `POST /api/forms/{id}/event` `{ev, expected_version}` (قطع = `ev:""`؛ فرم منتشرشده باید متوقف باشد؛ با پاسخ ثبت‌شده قفل؛ رویداد باید واقعی باشد؛ ممیزی `form.event_link`) |
| پاسخ‌های یک فرم | `GET /api/forms/{id}/responses` (+ `format=csv` با `fm_export`) |
| حضور و خروج از حضور | `POST /api/admin/attendance/responses/{rid}/check-in` / `undo-check-in` (دلیل + ممیزی؛ حضور فقط با پرداخت تأییدشده) |
| تصمیم رسید (تأیید دستی پرداخت کار صندوق) | `POST /api/admin/inbox/{task_id}/decision` (`receipt_approve`، دلیل الزامی، نسخه، ممیزی `workflow.decide`) و فایل رسید `GET /api/admin/inbox/{task}/files/{file}` |
| گواهی‌ها | `GET /api/admin/certificates?event_ref=` |
| فایل‌ها و رسانه‌ها، پرسش‌وپاسخ، دیدگاه‌ها، گزارش‌ها، یادآورها | زبانه‌های موجود پروندهٔ رویداد (بدون تغییر) |

### ۱.۴ کمبودهای واقعی که مسیر موجود ندارند (نیاز به نقطهٔ پایانی تازه، همه فقط‌خواندنی یا با همان قاعده‌های موجود)

1. هیچ مسیری «ثبت‌نام‌کنندگانِ یک رویداد» را با وضعیت ثبت‌نام + پرداخت + حضور نمی‌داد (فقط به‌ازای هر فرم یا هر کاربر).
2. هیچ مسیری پرداخت‌های یک رویداد را فهرست نمی‌کرد.
3. رسید بارگذاری‌شده از وب (`form_receipt_uploads`) برای پاسخ‌هایی که از بله ادعا نشده‌اند، در هیچ‌جای پنل دیده و تصمیم‌گیری نمی‌شد (کار صندوق فقط هنگام ادعای بلیت در بله ساخته می‌شود).
4. تصویر بلیت فقط با کوکی نشست خود فرد (`/api/public/forms/{id}/ticket-image`) ساخته می‌شد؛ مدیر راهی برای دیدن بلیت نداشت.
5. نتیجهٔ تجمیعی نظرسنجی/آزمون روی سرور محاسبه نمی‌شد (فرم‌ساز ردیف‌ها را نشان می‌دهد؛ کلید پاسخ/نمره‌دهی آزمون در مدل سرور وجود ندارد).

قرارداد تازه (فاز ۲ تا ۵؛ همگی زیر `/api/admin/events/{event_id}/…`، شناسهٔ رویداد و فرم سمت سرور اعتبارسنجی می‌شود و فرمِ رویداد دیگر ۴۰۴ می‌گیرد):

| مسیر | مجوز | کار |
| --- | --- | --- |
| `GET …/overview` | هر یک از `ev_create, ev_publish, fm_create, fm_responses, attendance, finance, certificate` | سرِ پرونده: رکورد رویداد، فرم‌های وصل‌شده با نوع/وضعیت/شمار پاسخ، تنظیمات ثبت‌نام از فرم اصلی (ظرفیت، لیست انتظار، قیمت پایه، روش پرداخت)، شمارنده‌های سروری |
| `GET …/registrations` | `fm_responses` یا `attendance` | فهرست ثبت‌نام‌کنندگان با خلاصهٔ سروری و صافی‌های `q / status / payment / attendance / form_id` و صفحه‌بندی |
| `GET …/registrations/{rid}` | همان | پروندهٔ فرد (همان سازندهٔ U4 بخش کاربران؛ پاسخ‌های نشان‌دار، همراهان، پرداخت با ماسک مالی، رسید، حضور) |
| `GET …/registrations/{rid}/receipt` | `receipt_approve` یا `finance` | فایل رسید وبِ همان پاسخ (`private, no-store`) |
| `GET …/registrations/{rid}/ticket-image` | `attendance` یا `fm_responses` | همان رندر بلیت عمومی با همان شرط‌ها (پذیرفته + پرداخت تأییدشده) |
| `POST …/registrations/{rid}/payment-decision` | `receipt_approve` | تأیید/رد رسید کارت‌به‌کارت با دلیل؛ اگر کار صندوق باز باشد همان `apply_admin_task_decision`؛ وگرنه روی `form_payments` با ممیزی (قبلی/جدید، دلیل، اقدام‌کننده)؛ تکرار = بدون تغییر |
| `GET …/payments` | `finance` | پرداخت‌های همهٔ فرم‌های این رویداد با نام فرد، مبلغ، وضعیت، زمان، شناسهٔ تراکنش، وضعیت رسید |
| `GET …/forms/{form_id}/summary` | `fm_responses` | تجمیع پاسخ‌های نظرسنجی/آزمون (شمار هر گزینه، میانگین عددی، شمار پاسخ) |

هیچ جدول یا مهاجرت تازه‌ای لازم نشد (همهٔ داده‌ها موجودند)؛ بنابراین مهاجرتی نوشته نشده است.

### ۱.۵ ماتریس فرم‌ها و قابلیت‌ها

| نوع فرم (`need`) | در پروندهٔ رویداد | پاسخ‌ها | پرداخت/بلیت/حضور | نتیجهٔ تجمیعی |
| --- | --- | --- | --- | --- |
| ثبت‌نام (`reg`, purpose=registration) | زبانه‌های ثبت‌نام‌کنندگان، پرداخت‌ها، بلیت و حضور | پروندهٔ فرد | بله (قاعده‌های موجود) | ــ |
| نظرسنجی (`survey`) | زبانهٔ نظرسنجی و آزمون | فهرست پاسخ‌ها | ندارد | شمار گزینه‌ها / میانگین |
| آزمون (`exam`) | همان زبانه | فهرست پاسخ‌ها | ندارد | شمار گزینه‌ها؛ **نمره‌دهی ندارد (کلید پاسخ در مدل سرور نیست → «نیازمند سرویس»)** |
| سایر (`other`) | زبانهٔ فرم‌ها با برچسب نوع | فهرست پاسخ‌ها | ندارد | ــ |
| خرید محصول ضبط‌شده (`recording_access`) | زبانهٔ موجود «مالی: ضبط‌شده و فروش» (دست‌نخورده) | ــ | سفارش‌ها | ــ |
