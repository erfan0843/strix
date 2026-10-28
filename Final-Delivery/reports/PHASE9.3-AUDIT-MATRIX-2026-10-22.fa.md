# فاز ۹.۳ — ممیزی نهایی و ماتریس تطبیق (پیش از کدنویسی)

- تاریخ: ۱۴۰۵/۰۷/۳۰ (2026-10-22) · شاخه `arena/840de336-strix` · مبنا: `90046ca` (= HEAD راه‌دور هنگام شروع؛ working tree تمیز؛ PR #1 باز)
- ورودی‌ها: گزارش‌های فاز ۷، ۸، ۹، ۹.۱، ۹.۲ + خواندن مستقیم کد (`backend/recordings.py`, `event_interaction.py`, `video_sources.py`, `certificates.py`, `app.py`, `account.js`, `admin.js`, `event-interaction.js`, `ui.js`, ربات `eventcert.py`/`certcenter.py`/`shared_certificates.py`).
- وضعیت‌ها: **✅ موجود و آزموده‌شده** · **🟡 ناقص (شکاف واقعی)** · **⚪ فقط رابط/متن** · **🔧 نیازمند زیرساخت یا سرویس بیرونی** · **⛔ خارج از دامنه**
- محیط این فاز: بدون اینترنت خروجی (پخش واقعی یوتیوب/آپارات و بلهٔ واقعی ناممکن)، بدون LibreOffice (PDF واقعی ربات ناممکن)، سرور پیش‌نمایش آزمایشی محلی + Chromium headless در دسترس.

## ماتریس

| قابلیت | وضعیت واقعی | منبع حقیقت | مدل و API | مسیر کاربر | مدیریت | مجوز | محدودیت | اقدام لازم (۹.۳) | آزمون پذیرش |
|---|---|---|---|---|---|---|---|---|---|
| ۱. خانه، بنرها، شمارشگر، صفحهٔ برنامه‌ها، صفحهٔ رویداد | ✅ (فاز ۷ + شمارشگر مشترک) | `site_content` + `public-data.js` | `GET /api/public/content`, `/api/public/events/{id}` | `home.html` → `events.html` → `event.html` | پنل: رویدادها و مطالب | `ev_create`/`ev_publish` | وضعیت انتشار ≠ ثبت‌نام؛ زمان از سرور | بدون تغییر | `events-page.test.mjs` 89 ✓، `event-page` در Node suite |
| ۲. مدل رویداد و `site_content` | ✅ | `SiteContentRecord('public').events[]` | همان | — | پنل محتوا | `ev_*` | یک منبع حقیقت؛ آرشیو = ردیف `event_recordings` وصل به همان `event_id` | بدون تغییر | pytest `test_site_content*`, `test_event_*` |
| ۳. فرم، پاسخ، ثبت‌نام، پرداخت، رسید | ✅ (۹.۱) | **فرم‌ساز** (`forms` + `form_responses` + `form_payments`); `forms.purpose ∈ {registration, recording_access}` + `forms.recording_id`; `form_snapshot.purpose` معنای پاسخ را قفل می‌کند | `POST /api/public/forms/{id}/responses` (خرید و ثبت‌نام یک مسیر)، تأیید رسید در کارتابل، webhook کیف پول بله در همان تراکنش | `event.html` CTA → `form.html?fid=…` (حالت خرید) → رسید/کیف پول → تأیید سروری | کارتابل مشترک + «ثبت‌نام و خریدها» | `receipt_approve`, `finance` | هیچ checkout موازی؛ `recording_orders` فقط دفترِ داخلی با `form_response_id` یکتا؛ قیمت/روش از تعریف فرم خوانده می‌شود (`commerce_for`) | **بدون نقص اثبات‌شده** → بدون تغییر کد | pytest `test_recordings_api.py` (۸ آزمون: بررسی سروری کارت‌به‌کارت، webhook idempotent، رد با دلیل، جدایی فرم ثبت‌نام/خرید، آرشیو با دسترسی فعال)، `test_forms_*` |
| ۴. `recordings.py` و وضعیت محصول | ✅ | `event_recordings.status ∈ draft/ready/published/sales_paused/archived` | `GET /api/public/events/{id}/recording`, پنل `/api/admin/recordings*` | قفسه در `events.html`؛ صفحهٔ محصول | بخش «محتوای ضبط‌شده» پنل | `ev_create`/`ev_publish` | مسدودکننده‌های انتشار (`purchase_form_*`, `no_published_session`, …) سروری | بدون تغییر | همان + `admin-recordings.test.mjs` |
| ۵. `event_resources` و دسترسی منابع | ✅ | `event_resources.access ∈ public/registered/attended/purchased/staff`؛ تصمیم در `resource_access_state` با `Participation` سروری | `GET /api/public/events/{id}/resources/{rid}/download` (بررسی مجوز در هر درخواست، Range برای `view`) | صفحهٔ رویداد/جلسات | «فایل‌ها و جلسات» | `ev_create` | فایل در DB ≤ ۸MB؛ خارجی فقط youtube/aparat/link | بدون تغییر | pytest `test_event_interaction_api.py`, `test_recordings_api.py` (دانلود بدون مجوز ۴۰۴/۴۰۳) |
| ۶. صفحهٔ فروش آرشیو و CTA | ✅ | CTA یگانه از سرور (`viewer_cta`: `login/free/buy/order_open/view/off_sale/staff_preview/unavailable`) | همان مسیر عمومی | دارندهٔ دسترسی «مشاهدهٔ جلسات» می‌بیند نه خرید | — | — | «ادامهٔ مشاهده» عمداً نیست (پیشرفت ذخیره نمی‌شود) | بدون تغییر | `event-recording.test.mjs` 71 ✓، شواهد ۹.۱ |
| ۷. حساب: «رویدادهای من» و «محتوای من» | 🟡 | ثبت‌نام‌ها: `GET /api/account/registrations`؛ کتابخانه: `GET /api/account/recordings` (**فقط ردیف‌های `recording_access`**) | همان | `account.html#events`, `#library`, `#payments` | — | نشست (`account_id` سروری) | (الف) آرشیوی که حاضرِ تأییدشده بدون خرید به آن مجاز است (`attendee_access`) در صفحهٔ رویداد باز می‌شود ولی **در «محتوای من» فهرست نمی‌شود**؛ (ب) «رویدادهای من» هیچ ارجاعی به آرشیو همان رویداد ندارد | **اقدام:** افزودن ردیف‌های courtesy (منبع `attended`) به `/api/account/recordings` با همان قواعد سروری؛ در «رویدادهای من» پیوند «مشاهدهٔ جلسات» برای ثبت‌نامی که آرشیو مجاز دارد + خلاصهٔ آرشیوهای در دسترس | pytest تازه + `account-recordings.test.mjs` + مرورگر |
| ۸. گواهی رویداد و `recording_completion` | ✅ (۹.۲) + 🟡 سیاست حضور | ربات: `eventcert` (شرط صدور `present` پیش‌فرض؛ گزینه‌های `none/paid/sessions/score/manual`)، `certcenter` (`cert_kind general|recording_completion`) | آینه: `POST /api/bot/certificates`, `GET /api/account/certificates`, `GET /api/admin/certificates?kind=` | «گواهینامه‌های من»؛ تحویل از ربات | پنل فقط می‌خواند؛ صدور/ابطال فقط در ربات | ادمین ربات؛ پنل `certificate` | شرط‌های `none` (فقط ثبت‌نام) و `paid` (فقط پرداخت) در `eventcert` می‌توانند گواهی‌ای صادر کنند که «حضور» را اثبات نمی‌کند؛ تغییر شرط بدون ثبت عامل | **اقدام:** هشدار صریح در انتخاب شرط `none/paid` (گواهی حضور نیست) + ثبت عامل/شرط در گزارش فعالیت؛ پیش‌فرض `present` حفظ | آزمون ربات تازه |
| ۹. مرکز صدور ربات و آینهٔ سرور | ✅ (۹.۲) | ربات = صادرکنندهٔ یگانه؛ سرور آینه | `shared_certificates.build_payload` | — | — | — | PDF واقعی نیازمند LibreOffice (در این محیط نیست) | بدون تغییر؛ محدودیت ثبت | ربات ۲۰۴ ✓؛ `test_certificates_api.py` |
| ۱۰. پخش YouTube/Aparat | ⚪/🔧 | `video_sources.parse` (شناسهٔ سروری، URL رسمی) | ۴۲۲ `invalid_video_source/unsupported_video_host/html_not_allowed/…` | قاب در صفحهٔ محصول؛ پیوند «باز کردن در سکو» | ویرایشگر منبع + پیش‌نمایش | `ev_create` | **پخش واقعی آزموده‌نشده** (بی‌اینترنت)؛ `load` ≠ پخش؛ IFrame Player API نیازمند اسکریپت بیرونی و آزمون واقعی | **اقدام:** وضعیت صادقانهٔ «پخش‌کننده بارگذاری شد؛ پخش تأیید نشده» پس از `load`؛ هشدار صریح Unlisted در ویرایشگر؛ CSP فعال نمی‌شود (فهرست قاب‌ها ثبت) | `event-recording.test.mjs`, `test_video_sources.py`؛ پخش واقعی = پس از استقرار |
| ۱۱. ذخیره‌سازی فایل، دانلود خصوصی، ویدئوی بلند | ✅ کوچک / 🔧 بلند | فایل در جدول `event_resources` (≤ ۸MB)، Range، مجوز در هر درخواست | همان دانلود | — | آپلود در پنل | `ev_create` | هیچ ذخیره‌سازی شیء/دیسک خصوصی، CDN، استریم یا DRM وجود ندارد | **اقدام:** فقط سند نیازمندی‌ها (`deployment/PRIVATE-VIDEO-STORAGE-REQUIREMENTS.fa.md`)؛ هیچ سرویس ساختگی | — |
| ۱۲. پرسش‌وپاسخ، دیدگاه، گزارش، اعلان | ✅ (فاز ۸ + ۹) | `event_questions/event_reviews/event_content_reports`, `user_notifications` (outbox، `pending/delivered/failed`) | `/api/public/events/{id}/questions|reviews`, پنل تعاملات | فقط داخل صفحهٔ رویداد؛ نشان `attendee`/`buyer` سروری | «تعاملات» پنل | `qa_*`/`ev_*` | اعلان = صف، نه تحویل؛ اعلان «انتشار جلسهٔ تازه» و «ثبت درخواست خرید» وجود ندارد (تصمیم: اضافه نمی‌شود، بدون نیاز اثبات‌شده) | بدون تغییر | pytest تعاملات، `test_recordings_api::test_buyers_review_…` |
| ۱۳. پنل مالک/مدیران، کارتابل، نقش‌ها | ✅ | `roles.py` + `require_permission` در هر مسیر | — | — | — | بک‌اند | مجوزها: `ev_create/ev_publish/receipt_approve/finance/certificate/rp_view` | بدون تغییر | `admin.test.mjs` 817 ✓؛ pytest مجوزها |
| ۱۴. مهاجرت‌ها، SQLite/PG، Node، mypy، مرورگر | ✅ | سر مهاجرت `0033` | — | — | — | — | — | رگرسیون کامل در پایان | بخش ۴ گزارش نهایی |

## تصمیم‌های این فاز (بدون انتظار تأیید جداگانه)
1. **هیچ سامانهٔ موازی**: خرید فقط از فرم‌ساز؛ `recording_orders` دفتر داخلی می‌ماند. کد خرید تغییر نمی‌کند (نقصی اثبات نشد).
2. **کتابخانهٔ حساب** ردیف‌های courtesy حاضران را با همان `has_content_access` سروری نشان می‌دهد (منبع `attended`)، بدون ساختن ردیف `recording_access` (دسترسی مشتق است، نه اعطاشده).
3. **پخش بیرونی**: IFrame Player API پیاده نمی‌شود (اسکریپت بیرونی غیرقابل‌آزمون در این محیط)؛ وضعیت صادقانه نمایش داده می‌شود؛ CSP فعال نمی‌شود.
4. **گواهی حضور**: هیچ مرکز/شرط تازه‌ای ساخته نمی‌شود؛ فقط هشدار و ثبت عامل برای شرط‌های غیرحضوری.
5. **ویدئوی بلند**: فقط سند نیازمندی.

## قاب‌های واقعی پروژه (برای CSP آینده)
| کجا | مبدأ قاب |
|---|---|
| `event-interaction.js` (صفحهٔ محصول) | `https://www.youtube-nocookie.com`, `https://www.aparat.com` |
| `admin.js` پیش‌نمایش منبع | همان دو |
| `ui.js` پخش‌کنندهٔ قدیمی رسانهٔ رویداد (`videoEmbedInfo`) | همان دو + `https://player.vimeo.com` + `https://www.dailymotion.com` |
| `ui.js` نمایش PDF رسانه | نشانی رسانه (می‌تواند بیرونی باشد) |
| `loading-preview.html` | `'self'` |
| دانلود فایل‌ها | `default-src 'none'; sandbox` روی پاسخ فایل (موجود) |
