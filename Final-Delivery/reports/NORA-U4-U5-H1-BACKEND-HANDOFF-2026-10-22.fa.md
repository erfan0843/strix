# تحویل کوتاه قراردادهای بک‌اند — U4 / U5 / H1

تاریخ: ۲۰۲۶-۱۰-۲۲ · شاخهٔ رابط: `arena/5705a11f-strix` · مبنا: `8a829f518599c61ca1b244dcce43c6852bee96ba`

این سند درخواست هماهنگی برای مسئول بک‌اند است؛ هیچ‌کدام از endpointهای پیشنهادیِ جدید در این سند به‌عنوان موجود فرض نشده‌اند. پاسخ‌های API باید از نشست/مجوز سرور استخراج شوند؛ شناسهٔ ارسالی مرورگر به‌تنهایی مجوز نیست.

## U4 — پاسخ‌های فرم ثبت‌نام متعلق به یک حساب

**وضعیت کد:** `GET /api/admin/users/{account_id}` با `us_view`، `Cache-Control: private, no-store` و scope مبتنی بر حساب، `registration_items` خلاصهٔ ثبت‌نام، پرداخت و حضور را برمی‌گرداند. پاسخ فرم/فیلدها برگردانده نمی‌شوند. `GET /api/account/registrations` فقط حساب جاری است و برای پنل ادمین قابل استفاده نیست.

**درخواست endpoint تکمیلی** (مسیر پیشنهادی؛ نیازمند تأیید بک‌اند):
- `GET /api/admin/users/{account_id}/registrations/{response_id}`
- مجوز: `us_view`؛ 401 بدون نشست، 403 بدون مجوز، 404 هم برای پاسخ ناموجود و هم پاسخ متعلق به حساب دیگر تا عدم افشای وجود. سرور باید هم‌زمان `account_id` پاسخ را با مسیر تطبیق دهد.
- ورودی: UUIDهای مسیر؛ بدون پارامتر شناسایی حساب از query یا نام کاربری.
- خروجی پیشنهادی: `{source:"shared_server_database", account_id, response_id, form:{id,name}, event:{id,title,date}|null, status, created_at, answers:[{field_id,label,value}]}`. پاسخ‌ها فقط از submission حساب هدف؛ حذف فیلدهای مخفی/حساس و دادهٔ حساب‌های دیگر. پرداخت و حضور فقط با فیلدهای واقعی و مجوزهای موجود، نه محاسبهٔ رابط.
- اگر API فهرست فعلی صفحه‌بندی ندارد، `GET /api/admin/users/{account_id}/registrations?limit&offset` نیز لازم است؛ فعلاً endpoint پرونده حداکثر ۵۰ مورد برمی‌گرداند و `total/has_more` ندارد.
- آزمون بک‌اند لازم: حساب A پاسخ دارد، حساب B ندارد؛ جزئیات متعلق به A؛ دسترسی به پاسخ B با مسیر A → 404؛ 401/403؛ پاسخ فاقد دادهٔ مخفی؛ حد صفحه‌بندی.

## U5 — اعلان‌های وابسته به حساب

**وضعیت کد:** `GET /api/admin/notifications?state&kind&limit&offset` صف سراسری با `rp_view` است. فیلد `account_id` در پاسخ ردیف‌ها، قابلیت فیلتر محسوب نمی‌شود. `GET /api/account/notifications` فقط حساب جاری و برای مدیر از مسیر پرونده قابل استفاده نیست.

**درخواست endpoint مدیریتی** (مسیر پیشنهادی):
- `GET /api/admin/users/{account_id}/notifications?limit&offset`
- مجوز: `us_view` (یا مجوز مشخص و موجود برای پرونده/اعلان؛ لطفاً مجوز جدید بی‌هماهنگی اضافه نشود). سرور باید مالکیت هر ردیف را با شناسهٔ مسیر محدود کند؛ پارامتر account_id اختیاری در endpoint سراسری کافی نیست.
- خروجی: `{source:"shared_server_database", items:[{id,kind,title,body,created_at,scope:"account"|"global"|"system",delivery_status,delivery_attempts,last_delivery_error,delivered_at,link}], total,limit,offset,has_more}`. فیلدهای تحویل فقط از مدل موجود؛ خطای شبکه و «بدون هویت بله» متمایز بمانند. اعلان عمومی/سیستمی اگر به کاربر نسبت داده می‌شود باید برچسب scope جدا داشته باشد؛ پیام عمومی به‌عنوان پیام خصوصی وانمود نشود.
- فقط GET و فقط‌خواندنی برای این مأموریت؛ ارسال/تلاش دوباره مجاز نیست.
- آزمون بک‌اند لازم: اعلان اختصاصی A، اعلان B مخفی از A، اعلان عمومی/سیستمی با scope صحیح، صفحه‌بندی، 401/403، پاسخ حساب ناشناخته.

## H1 — اساتید و کارکنان در منبع محتوای عمومی

**وضعیت کد:** `GET /api/owner/site-content` و `PATCH /api/owner/site-content` با `expected_version` و نشست مالک وجود دارند؛ `site_content.people` در `CONTENT_KEYS` و sanitizer `_person` تعریف شده است. sanitizer فیلدهای عمومی مجاز شامل `id,n,ini,r,role2,kind,bio,quote,where,yrs,courses,rate,tag,exp,links,photo,g,form,formTxt` را می‌شناسد؛ `kind` فقط `staff` یا teacher می‌شود. PATCH به شکل `{content:{people:[...]},expected_version:<integer>}` است و باید از API واحد استفاده کند، نه منبع دوم.

**تأیید بک‌اند درخواستی:**
- تأیید کنید GET مالک شامل تمام رکوردهای people قابل مدیریت است یا فقط projection عمومی؛ اگر فقط منتشرشده است، روش حفظ draft/hidden ویرایشگر چیست؟ PATCH فعلی `sanitize_site_content` ورودی partial را می‌پذیرد اما هنگام merge، حذف/بقای رکورد غیرعمومی باید با قواعد `retain_non_public_rows` سازگار باشد.
- مجوز مورد انتظار فعلی `require_owner` برای خواندن و `require_owner_write` برای نوشتن؛ مدیر نباید از طریق UI یا endpoint جدید مجوز بگیرد.
- فیلدهای معتبر/الزامی، معنای حذف/عدم انتشار، و اینکه ذخیرهٔ `people` فوراً در `/api/public/site-content` منتشر می‌شود، تأیید شود. جلوگیری از ID تکراری و CAS نسخهٔ `expected_version` باید حفظ شود.
- آزمون بک‌اند لازم: GET مالک/غیرمالک؛ PATCH مجاز با `people` و افزایش نسخه؛ 401/403؛ 409 نسخهٔ قدیمی؛ 422 فیلد/دادهٔ نامعتبر و ID تکراری؛ دسته‌های دیگر بی‌تغییر؛ مشاهدهٔ مقدار ذخیره‌شده در projection عمومی مطابق سیاست انتشار؛ عدم حذف پنهانی رکوردهای غیرعمومی.

## پیگیری بک‌اند (پیاده‌سازی مستقل پس از تحویل اولیه)

قراردادهای پیشنهادی بالا پیاده‌سازی شدند؛ فایل‌های backend تغییرکرده: `backend/app.py`, `backend/site_content.py` و آزمون‌های `backend/tests/test_admin_user_records_api.py`, `backend/tests/test_site_content_api.py`, `backend/tests/test_partner_retention.py`.

- **U4 فهرست:** `GET /api/admin/users/{account_id}/registrations?limit&offset` با `us_view`؛ `source`, `items`, `total`, `limit`, `offset`, `has_more`. فقط ثبت‌نام‌های اصلی (نه companion) که scope حساب از draft تأییدشدهٔ کاربر/هویت پیوندشده به دست می‌آید.
- **U4 جزئیات:** `GET /api/admin/users/{account_id}/registrations/{response_id}` با همان مجوز؛ تطبیق هم‌زمان response و account و 404 برای پاسخ غریبه/ناموجود. `answers` از snapshot فرم با کلیدهای موجود فیلدهای فرم ساخته می‌شود؛ ستون `col:false` و mobile/credential برگردانده نمی‌شود. فیلد پرداخت/رسید/حضور فقط مقادیر رکورد واقعی‌اند.
- **U5:** `GET /api/admin/users/{account_id}/notifications?limit&offset` با `us_view`; query مستقیماً روی `UserNotificationRecord.account_id` فیلتر می‌شود. هر ردیف `scope:"account"` است؛ صف سراسری جداست و هیچ endpoint نوشتن/ارسال اضافه نشده. پیوند نامعتبر قدیمی به null تبدیل می‌شود.
- **H1:** همان `GET/PATCH /api/owner/site-content`، نه جدول یا مخزن جدید. GET مالک علاوه بر people عمومی، ردیف‌های private/draft را با فیلدهای محتوایی allowlist‌شده و نشانگرهای وضعیت می‌دهد. PATCH همان `{content:{people:[...]},expected_version}` را با `require_owner_write`، کنترل CAS و فیلدهای وضعیت سخت‌گیرانه می‌پذیرد. ردیف‌های غیرعمومی حذف‌شده از payload با سازوکار نگه‌داری موجود حفظ می‌شوند. projection عمومی people را دوباره از allowlist می‌سازد و فلگ‌ها/اطلاعات ناشناخته را حذف می‌کند؛ فقط ردیف‌هایی که `_public_record` می‌پذیرد منتشر می‌شوند. بدون migration.

**آزمون‌های بک‌اند:** تمام `backend/tests`: **۳۶۷ passed، ۴ skipped**؛ Mypy: **۰ خطا در ۷۳ فایل**. موارد جدید شامل مالک/مدیر، عضو بی‌مجوز، صفحه‌بندی، پاسخ خالی/غریبه، فیلد مخفی، عدم نشت اعلان بین دو حساب، پیوند ناامن، حفظ draft people، 401 مالک و رد state/ID نامعتبر هستند. یک هشدار deprecation در TestClient/httpx موجود است. نتیجهٔ UI/مرورگر نقش‌محور هنوز منتظر اتصال فرانت‌اند است.

## وضعیت فرانت‌اند و آزمون

- پروندهٔ کاربر از API سروری موجود می‌خواند و وضعیت ثبت‌نامِ ناشناخته دیگر «پذیرفته» تلقی نمی‌شود. در پرونده توضیح افزوده شد که ردیف‌ها خلاصه‌اند و جزئیات پاسخ API ندارد؛ دادهٔ فرم ساختگی نیست.
- U5 در پرونده اکنون صریح می‌گوید شمار اعلان فقط شمارش است و فهرست امن موجود نیست؛ صف سراسری به پرونده وصل نمی‌شود.
- H1: بخش خواندنی اساتید/کارکنان از `GET /api/owner/site-content` با نشست مالک در همان بخش محتوای عمومی نمایش داده می‌شود؛ refresh و خطای خواندن مدیریت می‌شود. نوشتن تا پاسخ قرارداد draft/hidden و انتشار غیرفعال است؛ هیچ کنترل ذخیرهٔ محلی/پیام موفقیت ندارد.
- آزمون‌های UI فعلاً اجراشده: `admin-restore.test.mjs` (۵۵ بررسی، شامل وضعیت ناشناخته، توضیح محدودیت پاسخ U4، و عدم استفاده از صف عمومی/endpoint خودکاربر برای U5); `admin-partners-server.test.mjs` (۲۶ بررسی، شامل خواندن people از API مالک، خطای 401 و retry، بدون دکمهٔ ذخیره); `admin-rbac.test.mjs` و `node --check admin.js` موفق.
- پس از قرارداد بک‌اند باید آزمون‌های UI تکمیلی اجرا شوند: U4 جزئیات/صفحه‌بندی/خالی/خطا/ممنوعیت و عدم render پاسخ بیگانه؛ U5 جداسازی حساب و تمایز scope؛ H1 نوشتن واقعی، 409/422/403 بدون پاک‌شدن پیش‌نویس و بدون toast موفقیت. آزمون بدون API نباید با fixture به‌عنوان دادهٔ عملیاتی سبز شود.
