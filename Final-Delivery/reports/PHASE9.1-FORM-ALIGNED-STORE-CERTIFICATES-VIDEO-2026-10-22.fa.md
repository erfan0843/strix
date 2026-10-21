# فاز ۹.۱ — هم‌راستاسازی فروش آرشیو با فرم‌ساز، سیاست گواهینامه و پخش چندمنبعهٔ ویدئو

- تاریخ: ۲۰۲۶‑۱۰‑۲۲ (۱ آبان ۱۴۰۵) · شاخه: `arena/840de336-strix` · نقطهٔ شروع: `60894ee` (HEAD و origin یکسان، درخت کار پاک، PR شمارهٔ ۱ **باز** و merge‌نشده).
- این سند مکمل `PHASE9-RECORDED-CONTENT-STORE-2026-10-21.fa.md` است؛ فاز ۹ بازنویسی نمی‌شود. **بخش الف** پیش از هر تغییر کد نوشته شده و از خواندن کد واقعی در `60894ee` آمده است؛ **بخش ب** پس از پیاده‌سازی تکمیل می‌شود.
- قواعد ثابت: همان شاخه؛ بدون پروژه/پنل/فروشگاه/درگاه موازی؛ بدون merge/deploy/تغییر دادهٔ تولید؛ هر کامیت مستقل و بلافاصله push با بررسی SHA راه‌دور؛ «وجود کد ≠ کارکرد»؛ دادهٔ آزمایشی در شواهد؛ هیچ رمز/توکنی در گزارش یا Git.

---

## الف) ممیزی پیش از کدنویسی

### الف‑۱) آنچه کد فعلی واقعاً انجام می‌دهد (منبع: `backend/app.py`, `financials.py`, `responses.py`, `schemas.py`, `recordings.py`, `certificates.py`, `event_interaction.py`, `models.py`)

**فرم‌ساز و پرداخت فرم (پیش از فاز ۹ ساخته شده و آزموده است):**
- `forms.settings` منبع تجاری فرم است: `fin` (اقلام قیمت)، `groups`، `coupon`، `cap`، `enabledPaymentMethods` (`card_transfer`/`bale_wallet`)، `receiptReviewRequired`، `paymentCard` (`number/holder/bank`؛ فقط وقتی رسید لازم است به مرورگر می‌رود). مبلغ همیشه سمت سرور با `calculate_payment_amount()` از همین تنظیمات محاسبه می‌شود.
- مدل‌های فرم: `registration, questionnaire, survey, contest, exam, attendance, datacollect, order, election`؛ `need` از مدل مشتق می‌شود. بلیت/ثبت‌نام فقط برای `model=registration & need=reg` (`_form_ticket_eligible`)؛ «رویدادهای من» (`GET /api/account/registrations`) و فهرست حضور پنل فقط `model=registration` را می‌خوانند.
- کارت‌به‌کارت فرم: پاسخ `form_responses` + ردیف `form_payments(awaiting_receipt)` → بارگذاری رسید مرورگری (`POST /api/public/forms/{id}/receipt` → `form_receipt_uploads`, وضعیت `receipt_submitted`) → **وظیفهٔ بررسی (`admin_tasks.receipt_review`) فقط هنگام «ادعای بلیت در ربات بله» ساخته می‌شود** (`/api/bot/form-tickets/claim` → `_create_public_form_receipt_task`) → تصمیم مدیر در صندوق مشترک (`POST /api/admin/inbox/{task}/decision`, مجوز `receipt_approve`) → `apply_admin_task_decision` پرداخت را `paid_manual`/`rejected` می‌کند. شرط پیوند پاسخ به وظیفه: `ticket_claimed_by_bale_user_id == task.bale_user_id` و `draft.bot_bale_user_id == task.bale_user_id`؛ یعنی مسیر تأیید رسیدِ فرم به بلیت و ربات وابسته است.
- کیف پول بله فرم: `POST /api/public/forms/{id}/payment-intents` → `form_payments(pending)` با `invoice_payload` → وب‌هوک مشترک `/api/payments/bale/webhook/{token}` (پیشوند `nora_`) → پس از `inquireTransaction` پاسخ ساخته و پرداخت `paid` می‌شود؛ تراکنش تکراری در `form_payment_transactions` ثبت می‌شود.
- پیوند هویت: پیش‌نویس عمومی با `bind_public_draft_account()` به حساب واردشده (`draft.account_id`) می‌چسبد. `admin_tasks.bale_user_id` **NOT NULL** است (جدول مشترک با ربات).

**فروش محتوای ضبط‌شده (فاز ۹، `60894ee`):**
- `event_recordings.price/currency/bale_enabled/payment_card` قیمت و مقصد کارت را **جدا از فرم‌ساز** نگه می‌دارند؛ `POST /api/account/recordings/{id}/orders` سفارش مستقل می‌سازد؛ رسید با `PUT /api/account/recording-orders/{id}/receipt`؛ تصمیم در صف جداگانهٔ `POST /api/admin/recording-orders/{id}/decision`؛ شاخهٔ وب‌هوک `norac_`. ⇒ **مسیر تجاری موازی با فرم‌ساز** (دقیقاً همان چیزی که این فاز باید اصلاح کند). دلیل فاز ۹ («`form_payments` به فرم/پیش‌نویس نیاز دارد و نهایی‌سازی آن ثبت‌نام می‌سازد») درست توصیف شده بود، اما راه‌حل درست تفکیک نهایی‌سازی بر اساس **کاربرد فرم** است، نه مسیر مستقل.
- چیزهایی که درست‌اند و می‌مانند: `recording_access` (حق دسترسی یکتا به ازای حساب/محصول، منبع purchase/free/granted، انقضا)، بررسی دسترسی در نقطهٔ دانلود/پخش، اعطا/لغو با دلیل، اعلان‌ها، نشان «خریدار تأییدشده»، صف/دفتر سفارش‌ها و بازپرداخت با `finance`.

**گواهینامه‌ها:**
- سامانهٔ صدور = **ربات بله** (`certgen/certissue/eventcert/certbatch/certcenter`)؛ سرور فقط آینهٔ تأییدشده (`certificates`, `POST /api/bot/certificates`, `kind ∈ event/batch/form/manual/center`, وضعیت `issued/revoked`, `external_key` idempotent، `serial/full_code` یکتا، شمارندهٔ اعتبارسنجی). پنل وب فقط می‌خواند. هیچ مسیر صدور سروری نیست.
- آزمون/نمره‌دهی سروری: **وجود ندارد.** فیلدهای `scoreOn/weight/score` فقط در پیکربندی فیلد ذخیره و حتی در payload عمومی فرم (`public_form_payload`) به مرورگر فرستاده می‌شوند؛ هنگام ثبت پاسخ هیچ نمره‌ای محاسبه یا ذخیره نمی‌شود. ⇒ «تکمیل دوره بر اساس آزمون» قابل احراز سروری نیست.
- «پیشرفت مشاهده» ذخیره نمی‌شود (فاز ۹ عمداً نساخت).

**پخش جلسه‌ها:**
- `event_resources.kind ∈ {file, link}`؛ فایل در DB (≤ ۸MB، `video/mp4` مجاز)، `delivery=view` با Range؛ `link_url` فقط `http/https` کلی و فقط وقتی `allowed`. پخش‌کنندهٔ صفحه (`event-interaction.js`) فقط `<video src=/api/public/events/{id}/resources/{rid}/download>` دارد. هیچ پشتیبانی از آپارات/یوتیوب، هیچ allowlist میزبان، هیچ `embed_url` سروری.
- سرآیندهای امنیتی: `X-Content-Type-Options`, `Referrer-Policy: same-origin`, `X-Frame-Options: SAMEORIGIN` (یا `frame-ancestors` از `NORA_FRAME_ANCESTORS` برای پیش‌نمایش)، `Permissions-Policy`. **CSP کامل (`frame-src/script-src`) روی صفحه‌ها وجود ندارد**؛ بنابراین افزودن iframe نیازی به بازکردن CSP ندارد، ولی allowlist باید در کد اعمال شود. `Referrer-Policy: same-origin` یعنی به یوتیوب/آپارات Referer فرستاده نمی‌شود (ویدئوهای «محدود به دامنه» پخش نخواهند شد — مستند می‌شود، تغییر داده نمی‌شود).

### الف‑۲) تصمیم معماری (حداقل تغییر، بدون سیستم موازی)

| موضوع | تصمیم | چرا |
|---|---|---|
| منبع قیمت/روش/کارت مقصد | **فرم خرید** (`forms` با `purpose='recording_access'` و `recording_id`) — `fin`, `enabledPaymentMethods`, `receiptReviewRequired`, `paymentCard` همان فرم. محصول این مقادیر را **مشتق** نشان می‌دهد و با فرم خرید پیوندخورده دیگر قابل ویرایش در محصول نیست (۴۰۹ `commercial_settings_in_form`). | یک محل ذخیره؛ فرم‌ساز مرجع تجاری |
| شروع خرید | `form.html?fid=…` (CTA «خرید دسترسی» صفحهٔ محصول به همان فرم می‌رود؛ payload عمومی فرم محصول/رویداد را اعلام می‌کند) | مسیر استاندارد موجود |
| جدایی از ثبت‌نام | `purpose=recording_access` در سرور: بدون بلیت (`_form_ticket_eligible=False`), بدون `ticket-link`, خارج از `/api/account/registrations` و فهرست حضور، بدون ثبت `ticket_checked_in_at` | خرید ≠ ثبت‌نام ≠ حضور |
| `recording_orders` | **حفظ** به‌عنوان دفتر داخلی خرید/دسترسی، با `form_response_id` + `form_payment_id`؛ فقط سرور آن را از پاسخ/پرداخت معتبر فرم می‌سازد. مبلغ/روش از `form_payments` کپی می‌شود (snapshot حسابداری، نه منبع تنظیم). | تاریخچهٔ خرید، بازپرداخت، CSV مالی، اعلان |
| رسید کارت‌به‌کارت | همان `form_receipt_uploads` + همان صندوق `admin_tasks`؛ برای `recording_access` وظیفه **هنگام بارگذاری رسید** ساخته می‌شود (نه هنگام ادعای بلیت)، با هویت بلهٔ تأییدشدهٔ همان حساب (الزامی چون `admin_tasks.bale_user_id` NOT NULL و فاز ۹ هویت خریدار را به پیوند بله بسته است)؛ `apply_admin_task_decision` برای این کاربرد پاسخ را با `draft.account_id == task.account_id` پیدا می‌کند و پس از `paid_manual` دسترسی می‌دهد | سازوکار موجود و مجوز `receipt_approve` |
| کیف پول بله | همان وب‌هوک `nora_`؛ پس از استعلام موفق، اگر کاربرد فرم `recording_access` باشد → دسترسی (نه بلیت). شاخهٔ `norac_` و نقاط `orders/receipt/cancel/decision` فاز ۹ **حذف** می‌شوند (هرگز deploy نشده بودند؛ دادهٔ تولیدی ندارند) | حذف مسیر موازی |
| رایگان | فرم خرید بدون `fin` → پاسخ → دسترسی رایگان بدون ردیف پرداخت؛ بدون فرم → `claim` موجود. هیچ تراکنش ساختگی | |
| تغییر قیمت/وضعیت فرم با سفارش باز | قیمت هر `form_payments` در لحظهٔ ایجاد قفل است (رفتار موجود فرم‌ساز)؛ انتشار محصول پولی بدون فرم خرید منتشرشده مسدود (`purchase_form_required`)؛ مکث/بایگانی فرم خرید → CTA «فروش متوقف»؛ همه با ممیزی | |
| گواهی حضور | دست‌نخورده (ربات، `kind=event`)؛ خرید هرگز حضور نمی‌سازد | |
| گواهی پایان محتوا | `event_recordings.certificate_policy ∈ {none, manual}` (پیش‌فرض `none`). `auto/assessment` **ساخته نمی‌شود** چون نمره‌دهی سروری قابل‌اعتماد وجود ندارد. صدور دستی از همان مسیر ربات با `kind=recording` و عنوان «گواهی پایان محتوای آموزشی ضبط‌شده»؛ سرور فقط این kind را در آینه می‌پذیرد و در حساب/محصول نشان می‌دهد. بدون شبیه‌سازی پیشرفت/نمره | |
| ویدئو | `event_resources.kind += youtube, aparat`؛ ورودی URL/شناسه سمت سرور به شناسهٔ استاندارد تبدیل می‌شود (یوتیوب `[A-Za-z0-9_-]{11}`؛ آپارات hash `[A-Za-z0-9]{3,16}`؛ فقط میزبان‌های رسمی)؛ `embed_url` فقط سرور می‌سازد (`https://www.youtube-nocookie.com/embed/{id}`؛ `https://www.aparat.com/video/video/embed/videohash/{hash}/vt/frame`) و فقط وقتی `allowed`؛ هیچ HTML دلخواه ذخیره نمی‌شود؛ پخش‌کننده با بارگذاری/خطا/پیوند جایگزین؛ CSP باز نمی‌شود. صریح: جاسازی ≠ میزبانی خصوصی/DRM | |

### الف‑۳) ماتریس تطبیق «قبل» (`60894ee`)

دسته‌ها: **A** درست و پابرجا · **B** موجود ولی ناقص/موازی · **C** ظاهری/آزمایش‌نشده · **D** غایب

| # | قابلیت | قبل | شکاف | تغییر لازم |
|---|---|---|---|---|
| ۱ | قیمت/روش/کارت مقصد محصول از فرم‌ساز | **B** (در `event_recordings`) | دو محل ذخیره؛ فرم‌ساز دور زده می‌شود | فرم خرید + اشتقاق |
| ۲ | انتخاب کاربرد فرم (ثبت‌نام/خرید آرشیو) در فرم‌ساز | **D** | — | `forms.purpose` + `forms.recording_id` + UI builder |
| ۳ | `form.html` به‌عنوان شروع خرید | **D** | CTA به پنل سفارش داخلی می‌رفت | CTA → فرم؛ سربرگ محصول در فرم |
| ۴ | اعتبارسنجی سروری فرم↔محصول↔رویداد | **D** | — | در schema/publish/submit |
| ۵ | پاسخ/پرداخت/رسید/تأیید از سازوکار فرم | **B** (فرم: بله؛ محصول: مسیر جدا) | صف جداگانه | وظیفهٔ صندوق هنگام بارگذاری رسید + نهایی‌سازی بر اساس کاربرد |
| ۶ | خرید بدون ثبت‌نام/بلیت/حضور | **A** (فاز ۹) → باید با فرم هم **A** بماند | فرم‌ها بلیت می‌سازند | `purpose` در همهٔ نقاط بلیت/حضور/ثبت‌نام |
| ۷ | رسید بدون تأیید → بدون دسترسی | **A** | — | حفظ در مسیر فرم |
| ۸ | کیف پول بله فقط پس از وب‌هوک+استعلام | **A** (`norac_`) | شاخهٔ موازی | ادغام در شاخهٔ `nora_` بر اساس کاربرد |
| ۹ | تکرار callback → یک خرید/یک دسترسی | **A** | — | حفظ (`form_payment_transactions` + یکتایی `recording_access`) |
| ۱۰ | رایگان بدون تراکنش ساختگی | **A** | — | حفظ + فرم رایگان |
| ۱۱ | «رویدادهای من»/«محتوای من»/سفارش‌ها از سرور | **A** | سفارش‌ها باید به پاسخ فرم پیوند بخورند | `form_response_id` در نمای سفارش |
| ۱۲ | گواهی حضور فقط با حضور تأییدشده | **A** (ربات) | — | حفظ؛ آزمون «خرید حضور نمی‌سازد» |
| ۱۳ | گواهی پایان محتوا، فعال/غیرفعال صریح | **D** | — | `certificate_policy` + نمایش صادقانه |
| ۱۴ | تکمیل دوره/آزمون سروری | **D** (نمره‌دهی وجود ندارد؛ نمرهٔ گزینه‌ها حتی عمومی است) | — | **ساخته نمی‌شود**؛ فقط دستی با مجوز/دلیل/سابقه |
| ۱۵ | تمایز عنوان گواهی پایان دوره | **D** | — | `kind=recording` در آینه + عنوان ثابت در ربات |
| ۱۶ | صدور تکراری/لغو/صدور مجدد قابل ممیزی | **A** (ربات: `external_key`, `revoked`) | — | حفظ |
| ۱۷ | منبع ویدئو: فایل خصوصی | **A** | — | حفظ |
| ۱۸ | منبع ویدئو: یوتیوب/آپارات با اعتبارسنجی | **D** | — | kind جدید + regex + embed سروری |
| ۱۹ | پیش‌نمایش واقعی در پنل | **D** | — | iframe از `embed_url` سروری |
| ۲۰ | حالت‌های بارگذاری/خطا/غیرقابل جاسازی/پیوند جایگزین | **D** | — | پخش‌کنندهٔ چندمنبعه |
| ۲۱ | اطلاعات پخش خصوصی فقط پس از بررسی دسترسی | **A** (فایل) | برای خارجی باید همان‌طور باشد | `embed_url` فقط با `allowed` |
| ۲۲ | CSP/میزبان‌ها | **B** (CSP صفحه‌ای نیست) | — | allowlist در کد؛ بدون بازکردن |
| ۲۳ | رویداد برگزارشده بدون محصول منتشرشده ≠ قابل خرید | **A** | — | حفظ |
| ۲۴ | ثبت‌نام‌کنندهٔ قبلی و دسترسی (`attendee_access`) | **A** | — | حفظ؛ بازبینی |

### الف‑۴) مدل داده (مهاجرت `0033_form_aligned_store`, افزایشی و برگشت‌پذیر)

- `forms.purpose` (`registration` پیش‌فرض | `recording_access`), `forms.recording_id` (FK `event_recordings.id`, nullable, index). فرم خرید باید `event_id` همان رویداد محصول را داشته باشد (اعتبارسنجی سروری).
- `event_recordings.certificate_policy` (`none` پیش‌فرض | `manual`).
- `recording_orders.form_response_id`, `recording_orders.form_payment_id` (nullable, یکتا؛ برای ردیف‌های سفارش فرم‌محور).
- `event_resources.kind` ← CHECK جدید `('file','link','youtube','aparat')`؛ `link_url` برای دو kind جدید نشانی رسمی استاندارد را نگه می‌دارد (شناسه از آن مشتق می‌شود).
- downgrade: ردیف‌های `youtube/aparat` به `link` برمی‌گردند (نشانی حفظ می‌شود)، ستون‌ها حذف. آزمون روی SQLite و PostgreSQL.

### الف‑۵) ترتیب کامیت‌ها

۱) همین ممیزی → ۲) مدل + مهاجرت + آزمون → ۳) بک‌اند فرم خرید (schema/publish/public payload/submit/receipt/inbox/webhook/claim) + حذف مسیر موازی + آزمون API → ۴) فرم‌ساز و `form.html` و صفحهٔ محصول/حساب/پنل → ۵) سیاست گواهینامه (سرور + ربات + نمایش) → ۶) ویدئوی چندمنبعه (سرور + پنل + پخش‌کننده) → ۷) بازبینی یکپارچگی + رگرسیون کامل + شواهد مرورگر → ۸) بخش ب این گزارش + README.

---

## ب) نتیجهٔ پیاده‌سازی

*(پس از پایان پیاده‌سازی تکمیل می‌شود.)*
