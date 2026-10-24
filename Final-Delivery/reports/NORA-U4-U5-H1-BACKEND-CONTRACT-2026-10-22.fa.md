# قرارداد نهایی بک‌اند — U4 / U5 / H1 (پاسخ به سند تحویل رابط)

تاریخ: ۲۰۲۶-۱۰-۲۲ · شاخهٔ بک‌اند: `arena/840de336-strix` · مبنای مشترک: `8a829f5`
· پاسخ به: `NORA-U4-U5-H1-BACKEND-HANDOFF-2026-10-22.fa.md` (شاخهٔ رابط `arena/5705a11f-strix`، کامیت `885c27a`)

این سند منبع اتصال رابط است؛ همهٔ مسیرها/کدهای زیر در کد و آزمون‌های بک‌اند وجود دارند (فایل‌ها و SHA در بخش ۵).
قاعدهٔ مشترک هر سه: **مجوز از نشست سرور می‌آید؛ شناسهٔ مسیر فقط «کدام حساب/پاسخ» را انتخاب می‌کند** و هرگز مبنای دسترسی نیست.
پاسخ‌ها `Cache-Control: no-store` دارند. خطاها به شکل استاندارد FastAPI `{"detail": ...}` برمی‌گردند (رشته یا `{code,...}`).

---

## U4 — ثبت‌نام‌های (پاسخ‌های فرم) یک حساب

### U4-الف · فهرست صفحه‌بندی‌شده
`GET /api/admin/users/{account_id}/registrations?limit=20&offset=0`

| مورد | قرارداد |
|---|---|
| مجوز | `us_view` (مالک یا نقش دارای آن). بدون نشست → **401**؛ نشست عضو بدون نقش (حتی برای شناسهٔ خودش) → **403** |
| ورودی | `account_id` UUID مسیر؛ `limit` ۱..۱۰۰ (پیش‌فرض ۲۰)، `offset` ۰..۱٬۰۰۰٬۰۰۰؛ هیچ پارامتر شناسایی حساب دیگری پذیرفته نمی‌شود |
| ۴۰۴ | `user_not_found`: شناسهٔ نامعتبر، حساب ناموجود، یا حسابی بدون ورود واقعی (bale/phone) |
| ۴۲۲ | `limit`/`offset` خارج از بازه (اعتبارسنجی Query) |
| scope | همان scope پروندهٔ کاربر: پیش‌نویس‌های خودِ حساب + ردیف‌های قدیمی بله که سرور برای همین حساب تأیید کرده؛ **ردیفی که نام حساب دیگری دارد هرگز نمی‌آید**. فقط ثبت‌نام اصلی (نه ردیف همراه)، فقط فرم‌های `model=registration` و `purpose=registration` |
| خروجی | `{source:"shared_server_database", account_id, items:[…], total, limit, offset, has_more}` |
| هر item | `{id, form_id, form_name, event_id, event_title, event_date, status, payment_status|null, receipt_uploaded, ticket_checked_in, ticket_type:{id,name}|null, created_at}` — همان شکل `registration_items` در `GET /api/admin/users/{id}` به‌علاوهٔ `event_id` و `ticket_type`. **بدون `answers`**، بدون مبلغ/شناسهٔ تراکنش |

### U4-ب · جزئیات یک ثبت‌نام
`GET /api/admin/users/{account_id}/registrations/{response_id}`

| مورد | قرارداد |
|---|---|
| مجوز | `us_view` (۴۰۱/۴۰۳ مثل بالا) |
| ۴۰۴ | `user_not_found` برای حساب؛ `registration_not_found` برای: شناسهٔ نامعتبر، پاسخ ناموجود، **پاسخ متعلق به حساب دیگر**، ردیف همراه، یا پاسخ فرم غیر ثبت‌نام — همگی یک کد تا وجود رکورد افشا نشود |
| خروجی | همهٔ فیلدهای item فهرست + `source, account_id, response_id, form:{id,name,version}, event:{id,title,date}|null, registrant_name, answers:[…], companions:[{id,name,status,ticket_checked_in}], payment, finance_visible, receipt:{uploaded,task_id,task_status}, attendance:{checked_in,checked_in_at,checked_in_by:{kind,id}|null}, updated_at` |
| `answers` | **فقط** فیلدهای فهرست‌شده در `form_snapshot.fields` همان پاسخ (به ترتیب فرم)؛ کلیدهای ناشناخته حذف می‌شوند؛ پاسخ خالی حذف می‌شود. هر ردیف: `{field_id, label, type, value, masked}` |
| ماسک | `type=mobile` → `value:null, masked:"mobile", hint:"۴ رقم آخر"`؛ `type=nid` → `value:null, masked:"national_id", hint:""`. هیچ‌گاه شمارهٔ کامل یا کد ملی برنمی‌گردد (برای مالک هم) |
| `payment` | `null` اگر پرداختی نیست؛ وگرنه `{status, method}` و فقط با مجوز `finance` (الان یعنی مالک): `+ amount, currency, transaction_id`. `finance_visible` می‌گوید کدام حالت است — رابط چیزی محاسبه نکند |
| پرداخت/حضور | فقط از ستون‌های واقعی (`form_payments`, `ticket_checked_in_*`, `receipt_review_task_id`)؛ **خرید ≠ ثبت‌نام ≠ حضور** همچنان جدا |

### وضعیت endpoint قدیمی
`GET /api/admin/users/{account_id}` بدون تغییر است (همان `registration_items` خلاصه، حداکثر ۵۰). رابط برای صفحه‌بندی و جزئیات از دو مسیر بالا استفاده کند؛ `/api/account/registrations` (حساب جاری) در پنل استفاده نشود.

---

## U5 — اعلان‌های یک حساب (فقط‌خواندنی)
`GET /api/admin/users/{account_id}/notifications?limit=20&offset=0`

| مورد | قرارداد |
|---|---|
| مجوز | `us_view` (۴۰۱/۴۰۳ مثل U4). مجوز تازه‌ای تعریف نشده |
| فیلتر | **در سرور** با `user_notifications.account_id = {account_id}` مسیر؛ صف سراسری `/api/admin/notifications` دست‌نخورده و همچنان `rp_view` است و به پرونده وصل نمی‌شود |
| ۴۰۴ / ۴۲۲ | `user_not_found`؛ `limit`/`offset` نامعتبر |
| خروجی | `{source, account_id, items:[…], total, limit, offset, has_more}` |
| هر item | `{id, kind, title, body, link|null, created_at, delivered_at|null, read, delivery_status, delivery_state, delivery_attempts, last_delivery_error|null, scope, has_bale_identity, source_task_id|null}` — `bale_user_id`، `file_refs` و `account_label` حذف شده‌اند |
| `delivery_state` | `queued` / `retrying` / `delivered` / `failed` (همان قاعدهٔ outbox؛ صف ≠ ارسال ≠ تحویل). `last_delivery_error = "no_bale_identity"` یعنی حساب هویت بلهٔ تأییدشده ندارد — خطای شبکه نیست؛ `has_bale_identity:false` همراه آن می‌آید |
| `scope` | `"account"`: متن برای همین حساب نوشته شده (تصمیم کارتابل `profile_*`/`receipt_*`، `recording_access`، `recording_order`، `recording_purchase`، `certificate`، `event_qa_answer`). `"audience"`: ارسال گروهی با متن یکسان به چند حساب (`recording_content` — انتشار محتوای تازه برای خریداران/حاضران). **مقدار `global`/`system` وجود ندارد**: در مدل داده هیچ جدول اعلان عمومی/سیستمی نیست و همهٔ ردیف‌ها به یک حساب آدرس‌دهی شده‌اند؛ رابط نباید چنین دسته‌ای نمایش دهد |
| عملیات | فقط GET. ارسال/تلاش دوباره روی این مسیر نیست (تلاش دوباره فقط `POST /api/admin/notifications/{id}/retry` با `ev_publish`، خارج از این مأموریت) |

---

## H1 — اساتید و کارکنان (`site_content.people`)

**هیچ endpoint تازه‌ای ساخته نشد؛** منبع همان سند واحد `site_content` است. رفتار واقعی بررسی و با آزمون پین شد:

| مورد | رفتار تأییدشده |
|---|---|
| خواندن | `GET /api/owner/site-content` — فقط نشست مالک (`require_owner`). مدیر/عضو/ناشناس → **401** (نه ۴۰۳؛ چون نشست مالک وجود ندارد). خروجی `content.people` **projection منتشرشده** است؛ ردیف‌های ذخیره‌شدهٔ `hidden/pend/pub:false/status:draft…` در آن نیستند |
| نوشتن | `PATCH /api/owner/site-content` با بدنهٔ دقیق `{"content":{"people":[…]},"expected_version":<int>}` — `require_owner_write` (Origin + `X-CSRF-Token` از کوکی `nora_csrf`). بدون CSRF → **403**؛ بدون نشست مالک → **401**. هیچ کلید دیگری در بدنه پذیرفته نمی‌شود (→ 400 `invalid_site_content_request`) |
| نسخه | CAS: `expected_version` باید برابر نسخهٔ فعلی باشد؛ وگرنه **409** `{"code":"site_content_version_conflict","current_version":N}`. موفق → `version = N+1`؛ نسخه از نوع غیر int → 422 `invalid_site_content_version` |
| ۴۲۲ | `duplicate_site_content_id` (دو ردیف با یک `id`)، `unexpected_site_content_fields` (کلید ناشناخته در `content`)، `invalid_site_content_records` (`people` غیرآرایه یا بیش از سقف)، `empty_site_content_update` (`content` خالی) |
| فیلدهای شخص | `id` (الزامی، ≤۱۰۰)، `n` (الزامی، ≤۱۶۰)، `ini`, `r`, `role2`, `kind` (`staff` یا هر چیز دیگر → `teacher`), `bio`, `quote`, `where`, `yrs`, `courses`, `rate`, `tag`, `exp[]`, `links[{k,v}]` (نرمال می‌شوند؛ مثلاً `mail` → `mailto:`), `photo` (URL یا data-image), `g`, `form`, `formTxt`. هر فیلد دیگر (تلفن، ایمیل خصوصی، token…) **حذف** می‌شود و هرگز در سند ذخیره نمی‌شود |
| **بدون پیش‌نویس** | برای `people` حالت draft/hidden قابل ایجاد از API **وجود ندارد**: ردیفی با `hidden/pend/pub:false/status∈{draft,…}` پذیرفته نمی‌شود. هر ردیف پذیرفته‌شده **در همان درخواست در `/api/public/site-content` منتشر می‌شود** (`updated_at`/`version` یکسان). رابط باید این را صریح بنویسد («ذخیره = انتشار فوری») و گزینهٔ «پنهان/پیش‌نویس» ارائه ندهد |
| ردیف‌های ردشده (افزوده شد) | پاسخ PATCH اکنون `rejected_rows` دارد: `{}` یا `{"people":[{"index":i,"id":"…","reason":"non_public"|"missing_required_fields"|"invalid_row"}]}` (و همین برای سایر دسته‌ها). پیش از این sanitizer چنین ردیف‌هایی را **بی‌صدا** حذف می‌کرد؛ اکنون رابط باید اگر `rejected_rows.people` خالی نبود، به‌جای «ذخیره شد» هشدار دهد. خودِ ذخیره تغییر نکرده (ردیف‌های معتبر ذخیره می‌شوند) |
| حذف / پنهان‌سازی | حذف = نیاوردن `id` در آرایه؛ ردیف عمومی از سند و سایت حذف می‌شود (کپی پنهان نگه داشته نمی‌شود). فرستادن `hidden:true` روی یک شخص عمومی = حذف آن از فهرست عمومی + ثبت در `rejected_rows` — پس «پنهان‌کردن» در رابط نباید وجود داشته باشد |
| نگهداری رکورد غیرعمومی | ردیف‌های غیرعمومیِ از قبل ذخیره‌شده (داده‌های قدیمی/نوشتار مستقیم) در هر ذخیرهٔ `people` **حفظ** می‌شوند (`retain_non_public_rows`)، نه در خروجی مالک دیده می‌شوند و نه در سایت؛ از پنل قابل ویرایش/حذف نیستند (محدودیت شناخته‌شده؛ برای تغییرشان مسیر جداگانه و تصمیم لازم است) |
| سایر دسته‌ها | ذخیرهٔ فقط-`people` به `events/articles/partners/banners/cooperation/library` دست نمی‌زند (آزموده شد) |
| ممیزی | `site_content.update` با کلیدها و نسخهٔ جدید ثبت می‌شود |

راهنمای رابط برای H1: `GET` → ویرایش در حافظه → `PATCH` با `expected_version` همان GET → در ۲۰۰: فهرست را از `content.people` پاسخ بازسازی کن (نه از حالت محلی) و `rejected_rows.people` را نشان بده؛ در ۴۰۹: پیش‌نویس کاربر را نگه دار، `current_version` را بگیر و «بارگذاری دوباره و تطبیق» بخواه؛ در ۴۲۲/۴۰۱/۴۰۳: بدون toast موفقیت، پیام همان کد. اعتبارسنجی سمت کلاینت: `id` یکتا و `n` غیرخالی قبل از ارسال.

---

## ۴. وضعیت اعلام‌شده
- بک‌اند U4/U5: **پیاده‌سازی و آزموده‌شده** (SQLite + PostgreSQL). رابط هنوز وصل نیست → **U4/U5 «کامل» نیستند** تا اتصال رابط در شاخهٔ دوم و آزمون یکپارچه.
- بک‌اند H1: **بدون endpoint تازه؛ رفتار تأیید و پین شد + `rejected_rows` افزوده شد.** ویرایشگر رابط می‌تواند با این قرارداد ذخیره را فعال کند؛ تا آن زمان H1 هم «کامل» نیست.
- دسترسی‌های مالک/مدیر با آزمون سروری پوشش داده شد؛ هیچ مجوز جدیدی اضافه نشد.

## ۵. فایل‌های تغییرکرده و آزمون‌ها
- `Final-Delivery/website/nora-ui/backend/app.py` — سه endpoint جدید (`/api/admin/users/{id}/registrations`, `…/registrations/{response_id}`, `…/notifications`) + کمکی `_rejected_content_rows` و فیلد `rejected_rows` در پاسخ PATCH محتوای مالک. بدون مهاجرت، بدون تغییر مدل.
- `backend/tests/test_admin_user_file_api.py` (جدید، ۳ آزمون): ۴۰۱/۴۰۳/۴۰۴/۴۲۲، صفحه‌بندی، حساب خالی، پاسخ حساب دیگر → ۴۰۴، ردیف همراه و فرم غیرثبت‌نام خارج از فهرست، ردیف قدیمی بلهٔ تأییدشده داخل فهرست، ماسک تلفن/کد ملی، حذف کلید ناشناخته، مالی فقط با `finance`، endpoint قدیمی بدون تغییر؛ اعلان‌ها: جداسازی حساب، `scope`، `delivery_state`، `no_bale_identity`، صفحه‌بندی، فقط‌خواندنی، صف سراسری دست‌نخورده.
- `backend/tests/test_site_content_people_editor.py` (جدید، ۱ آزمون): ۴۰۱ مدیر/عضو/ناشناس، ۴۰۳ بدون CSRF، ذخیرهٔ people و انتشار فوری، ۴۰۹، ۴۲۲ (تکراری/کلید ناشناخته/نسخه/خالی/غیرآرایه)، `rejected_rows`، حفظ ردیف پنهان قدیمی، عدم تغییر سایر دسته‌ها، حذف با نیاوردن id، عدم ذخیرهٔ فیلدهای خصوصی.
- نتایج (کد خروج ۰): pytest SQLite **366 passed**؛ pytest با PostgreSQL (pgserver) **371 passed**؛ mypy **0 خطا / 73 فایل**. آزمون‌های قبلی تغییر نکرده‌اند.

## ۶. بررسی زنده روی پیش‌نمایش (سرور آزمون روی همین کد، پایگاه آزمایشی)
- یک ثبت‌نام آزمایشی برای حساب `qa-free` روی فرم ثبت‌نام رویداد آینده ثبت شد (بدون همراه؛ فرم همراه ندارد).
- مدیر (`us_view`، بدون `finance`): فهرست A → ۱ مورد با `event_id`/وضعیت؛ جزئیات → پاسخ برچسب‌دار «نام کامل»، `payment:null`, `finance_visible:false`. مالک: `finance_visible:true`.
- همان `response_id` زیر مسیر حساب B → **404**؛ ناشناس → **401**؛ endpoint قدیمی پرونده همچنان ۱ ردیف خلاصه.
- اعلان‌ها: `qa-buyer` ۳ ردیف (`event_qa_answer`, `recording_access`, `recording_purchase`؛ همه `scope:"account"`, `queued`)، سایر حساب‌ها فقط ردیف‌های خودشان؛ صف سراسری دست‌نخورده.
- H1: PATCH مالک با یک ردیف `hidden:true` → نسخه ۴→۵، `rejected_rows.people=[{index:0, reason:"non_public"}]`، فهرست عمومی بدون تغییر؛ PATCH مدیر → 401 `authentication_required`؛ نسخهٔ کهنه → 409 با `current_version:5`؛ `/api/public/site-content` همان نسخهٔ ۵.
- توجه: پاسخ‌های فرم خرید (`purpose=recording_access`) عمداً در U4 نیستند (خرید ≠ ثبت‌نام)؛ مسیرشان همان «محصولات/سفارش‌ها» است.
