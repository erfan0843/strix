# پاسخ‌گیری سروری نورا

این پیاده‌سازی یک برنامهٔ واحد FastAPI است: همان فرایند، UI موجود از `nora-ui/` را ارائه می‌کند و API فرم و پاسخ را اجرا می‌کند. مخزن یا سرویس موازی ساخته نشده است. پاسخ‌دادن به فرم عمومی به حساب کاربری، ورود یا نمایه وابسته نیست.

> برای نصب و اجرای بدون سرویس خارجی، [راهنمای نصب، اجرا و تست محلی](../../../../LOCAL-DEVELOPMENT.fa.md) را ببینید؛ launcher فقط DB توسعهٔ داخل `.local` را می‌پذیرد.

## قابلیت‌های پیاده‌شده

- نشست مالک با کوکی `HttpOnly` و `SameSite=Strict`، CSRF، و محدودیت تلاش ورود. مالک و مجوز هر عملیات از نشست سرور تعیین می‌شوند؛ مرورگر نمی‌تواند `owner_id` یا وضعیت انتشار را تحمیل کند.
- دکمهٔ «ورود/ثبت‌نام» ناوبری ابتدا `account.html` را به‌صورت مهمان باز می‌کند؛ خانه، رویدادها، محتوای عمومی و پشتیبانی بدون ورود در دسترس‌اند. بخش‌های خصوصی از همان‌جا ورود امن می‌خواهند و backend مجوز را مستقل بررسی می‌کند.
- ثبت‌نام فرم عمومی برای مهمان آزاد است؛ فقط با نشست وب معتبر، پیش‌نویس به `account_id` همان نشست وصل می‌شود. `GET /api/account/registrations` خلاصهٔ ثبت‌نام‌های همان حساب را می‌دهد؛ سابقهٔ قدیمی بدون پیوند امن با تلفن، نام یا شناسهٔ بله حدس زده نمی‌شود.
- `login.html` به‌طور پیش‌فرض فقط ورود عضو با OTP واقعی را نشان می‌دهد: شماره به `POST /api/auth/phone-otp/request` می‌رود و کد شش‌رقمی با `POST /api/auth/phone-otp/verify` در سرور بررسی می‌شود. Safir کد را با پیامک به شماره می‌رساند؛ صفحه CAPTCHA، کد ثابت یا نشست محلی نمی‌سازد و شماره/کد را در `localStorage` یا نشست مرورگر نمی‌نویسد. وضعیت ارسال پیامک نمایش داده می‌شود و این ورود به حساب یا Mini App بله لینک نمی‌دهد. Mini App و روش‌های عضوِ دیگر در UI این صفحه ارائه نمی‌شوند. مالک و مدیران یک فرم مشترک نام‌کاربری/گذرواژه دارند؛ `/api/auth/staff-login` هویت را در backend تشخیص می‌دهد و نشست جداگانهٔ `owner` یا `manager-password` می‌سازد. ورود عضو با OTP همچنان مسیر جداست؛ endpointهای اختصاصی `/api/auth/login` و `/api/auth/manager-login` نیز حفظ شده‌اند.
- نقش حساب پس از تأیید هویت در جدول `account_roles` و فقط با نشست مالک تغییر می‌کند؛ OTP هیچ نقشی نمی‌سازد و به‌تنهایی API مدیریتی وب را باز نمی‌کند. مالک فقط برای حساب دارای نقش `manager` یا `club-supervisor` می‌تواند با `/api/owner/accounts/{account_id}/manager-credentials` اعتبارنامهٔ مدیر تعیین کند. نام کاربری یکتا است، گذرواژه با scrypt هش می‌شود، پاسخ API هرگز هش/گذرواژه را برنمی‌گرداند و تغییر یا حذف اعتبارنامه/نقش نشست‌های گذرواژه‌ای مدیر را باطل می‌کند. `/api/auth/manager-login` محدودیت تلاش دارد و نقش/مجوز را از همان نشست و پایگاه‌دادهٔ سرور می‌خواند؛ API مدیریتی وب، نشست `manager-password` یا مالک را می‌پذیرد؛ اختیارهای مالی، تنظیمات و نقش‌گذاری همچنان فقط برای مالک است.
- پل هویت ربات در `POST /api/bot/identity` فقط با توکن سرویسِ سروربه‌سرور کار می‌کند و نقش همان شناسهٔ بله را از همین پایگاه‌داده می‌خواند؛ این مسیر هنوز اعلان یا تغییر داده‌ای نمی‌فرستد.
- snapshot عمومی رویدادها، پروفایل‌ها، مطالب، نهادها و بنرها در پایگاه‌داده؛ پنل فقط پس از ورود مالک و انتخاب صریح دسته‌ها آن‌ها را با نسخهٔ مورد انتظار همگام می‌کند. API سرور فیلدها را allowlist می‌کند و شمار ثبت‌نام، کد دعوت، اطلاعات خصوصی CRM و پیش‌نویس‌ها را عمومی نمی‌کند.
- ایجاد و ویرایش پیش‌نویس‌های نسخه‌دار فرم در همان پایگاه‌دادهٔ سامانه؛ ساخت idempotent است و ویرایش با `expected_version` از بازنویسی هم‌زمان جلوگیری می‌کند.
- انتشار و توقف صریح پاسخ‌گیری از `create.html`. هر فرم تازه `draft` است و تا انتشار مالک، پیوند عمومی پاسخ‌گو نیست.
- صفحهٔ عمومی `form.html` از دادهٔ فرم منتشرشدهٔ سرور bootstrap می‌شود. پیوند عمومی فاقد `preview=1` است؛ پیش‌نمایش محلی به‌اشتباه به‌عنوان ثبت آنلاین نمایش داده نمی‌شود.
- روش پرداخت عمومی فقط از انتخاب سازنده در تنظیم همان فرم می‌آید: کارت‌به‌کارت همراه رسید و بازبینی دستی، یا کیف پول بله. کارت‌به‌کارت قبل از تأیید مدیر بلیت نمی‌دهد. کیف پول بله پیش‌فرض خاموش است و فقط با bot اختصاصی پرداخت، provider token، راز webhook و URL عمومی HTTPSِ معتبر قابل انتشار می‌شود؛ webhook مستقل در همین backend، `pre_checkout_query` را پاسخ می‌دهد و پرداخت موفق را با `inquireTransaction` از سرور بله می‌سنجد. وضعیت مرورگر به‌تنهایی معتبر نیست. تراکنش‌های provider در جدول یکتا و idempotent نگه‌داری می‌شوند؛ این مسیر از handler پرداخت بات قدیمی و SQLite آن استفاده نمی‌کند.
- پیش‌نویس ناشناس با نشست تصادفیِ مختص همان فرم، کوکی `HttpOnly`، و نگه‌داری hash نشست در DB. پاسخ اصلی و جواب‌های جداگانهٔ همراهان با debounce ذخیره و از همان مرورگر بازیابی می‌شوند.
- ثبت نهایی پس از اعتبارسنجی دوبارهٔ پاسخ اصلی و پاسخ هر همراه بر اساس نوع، شناسه، شرط نمایش، اجباری‌بودن، گزینه‌ها، قالب، طول و قواعد کیفیتِ آفلاین در سرور. نام شخصِ آشکارا نامعتبر (از جمله نام نمونه یا واژهٔ متشکل از یک حرف تکراری) و تاریخ تولد آینده رد می‌شوند. الگوهای مشکوک در متن آزاد و مقدارهای ساختاریافته—مانند جای‌نگهدار، دنبالهٔ صفحه‌کلید فارسی/لاتین، تکرار نویسه/الگو/واژه یا ایمیل نمونه—در رابط هشدار غیرمسدودکننده می‌دهند؛ سرور پاسخ را صرفاً به‌خاطر این هشدارها رد نمی‌کند. تاریخ تولدِ امروز در رابط تأیید صریح می‌خواهد، اما API آن را مجاز می‌داند تا تولد واقعی نوزاد ناممکن نشود؛ تاریخ‌های عمومی رویداد مشمول قاعدهٔ تولد نیستند. پاسخ دانشگاه خارج از snapshot محلی همچنان مجاز است. این بررسی‌ها در `backend/form_quality.py` و `form-quality.js` بدون AI یا درخواست بیرونی اجرا می‌شوند؛ جزئیات و مرزها در [`QUALITY-VALIDATION.md`](../QUALITY-VALIDATION.md) آمده است. پاسخ‌ها در `form_responses` و همراه با snapshot نسخه/پرسش‌ها می‌مانند؛ ثبت دوبارهٔ همان نشست رکورد تازه نمی‌سازد. مدیر مجاز، پاسخ‌های همراه را در جزئیات همان ثبت‌نام می‌بیند.
- وضعیت `accepted` یا `waitlisted` بر اساس ظرفیت و صف در سرور تعیین می‌شود. برای ثبت‌نام `accepted`، مدل ثابت یا یک انتخاب یکنواخت از میان مدل‌های تصادفی در همان `form_snapshot` پاسخ ذخیره می‌شود؛ retry و بازیابی همان مدل را برمی‌گردانند. پاسخ `waitlisted` نه مدل می‌گیرد و نه بلیت؛ صف انتظار خودکار به پذیرش ارتقا نمی‌یابد.
- مشاهدهٔ پاسخ برای نقش دارای `fm_responses` و حذف پاسخ فقط با نشست مالک؛ پاک‌کردن نشست/پاسخ هم از همان مرورگر ممکن است. پس از وجود پاسخ، تعریف سؤال‌ها قفل است تا پاسخ ذخیره‌شده به نسخهٔ تازه‌ای نسبت داده نشود؛ توقف پاسخ‌گیری فقط با مالک انجام می‌شود.
- محدودیت درخواست عمومی و پاک‌سازی پیش‌نویس‌های منقضی‌شدهٔ بدون پاسخ.

## مرزها و محدودیت‌های آگاهانه

انتشار فقط وقتی پذیرفته می‌شود که فرم با مسیر سروری پشتیبانی‌شده سازگار باشد. برای ثبت‌نام، مبالغ/کوپن و فقط روش‌هایی که سازنده در همان فرم فعال کرده پشتیبانی می‌شوند: کارت‌به‌کارت نیازمند کارت معتبر، رسید و بازبینی دستی است؛ کیف پول بله نیازمند پیکربندی کامل و امن در backend است و تا آن زمان انتشار فرمِ انتخاب‌کنندهٔ آن متوقف می‌شود. روش‌های سفارشی/درگاه، کد دعوت یا محدودیت رویداد، زمان‌بندی، رسانه یا فایل و تأیید شماره/هویت در مسیر عمومی اجرا نمی‌شوند. همراه فقط با `guestsOn=true`، `compFields=name-mobile-answers` و تعداد کل ۲ تا ۱۰ نفر فعال می‌شود؛ برای هر همراه، نام، موبایل یکتا و پاسخ مستقل هر پرسش اعتبارسنجی می‌شود. فرم‌هایی با مدل‌های دیگر همراه در وب منتشر نمی‌شوند. ربات بله فعلاً همراهان را فهرست نمی‌کند و مسیرهای نوشتن مستقیم آن‌ها را نمی‌پذیرند. فرم سفارش نیز منتشر نمی‌شود. نوع فیلد ناشناخته یا تنظیم تأیید فعال از سمت سرور رد می‌شود.

endpoint ورود Mini App (`POST /api/auth/bale-mini-app`) فقط هویت بله را احراز می‌کند و در پوستهٔ مشترک `ui.js` مصرف می‌شود؛ چون `initData` یک‌بارمصرف است، پوسته اول وضعیت نشست را می‌پرسد و فقط در نبود نشست امضا را می‌فرستد. فرم ورود وب (شماره/گذرواژه) جای خودش را دارد و جایگزین نشده است. پیوند امن هویت بله به حساب موجود هم از راه `GET/POST/DELETE /api/account/identities` انجام می‌شود. OTP وب فقط پس از تنظیم کلید و شناسهٔ لازم برای API پیامکی Safir روی سرور، کد را با پیامک می‌فرستد و هیچ ارسال پیام/اعلان عمومی را فعال نمی‌کند. صفحهٔ ورود وب مسیر آزمایشی، کد ثابت یا نشست محلی ندارد. پرداخت زنده در حالت پیش‌فرض خاموش است؛ کیف پول بله فقط وقتی backend پیکربندی معتبرِ bot اختصاصی، provider token و webhook را ببیند برای فرم‌های منتخب قابل انتشار می‌شود. callback پرداخت در مسیر webhook همین برنامه پردازش و با استعلام server-side بررسی می‌شود؛ به handler قدیمی بات یا SQLite آن وابسته نیست. پیکربندی کیف پول بله اختیاری و مستقل از `NORA_BALE_BOT_TOKEN` (فقط Mini App) و `NORA_BOT_SERVICE_TOKEN` (API ربات/claim بلیت) است. نبود این کلیدها startup وب FastAPI را متوقف نمی‌کند؛ فقط endpointهای وابسته با 503 بسته می‌مانند. سرویس جداگانهٔ `bale-bot/nora_bot/` برای اجرای خودش به توکن بله و تنظیم API مشترک نیاز دارد. هیچ secret را در HTML یا مرورگر نگذارید. تأیید پیش‌پرداخت به‌تنهایی ثبت یا پرداخت نهایی نیست. کارت‌به‌کارت نیز فقط پس از تأیید دستی به بلیت واقعی می‌رسد. صف خروجی و ارسال عمومی اعلان همچنان خاموش‌اند. بلیت فرم ثبت‌نامِ پذیرفته‌شده از پاسخ مشترک ساخته می‌شود. همان تصویر واقعیِ renderer بلیت در صفحهٔ وب، فقط برای نشست امن همان فرم و پس از تأیید پرداخت/ثبت فیش لازم، قابل نمایش و دانلود است؛ پیوند امن ربات بله نیز حفظ می‌شود. پیوند موقت پیش از تأیید دستی فقط بازبینی رسید را آغاز می‌کند و بلیت نمی‌دهد. پاسخ `waitlisted` نه تصویر و نه فایل بلیت نمی‌گیرد. مالک می‌تواند از پنل، برای حساب تأییدشده با بله یا OTP نقش مدیر/سرپرست باشگاه تعیین کند؛ حسابِ بی‌نقش همچنان دسترسی مدیریتی ندارد. ورود نام کاربری/گذرواژهٔ مدیر فقط پس از تعیین نقش و اعتبارنامهٔ مالک ممکن است؛ ورود OTP نیز به‌تنهایی هیچ نقشی نمی‌دهد. برای هویت‌گذاری در ربات باید شناسهٔ بله جداگانه به همان حساب متصل باشد. وضعیت `/api/outbox` خاموش است و هیچ ارسال خارجیِ ناخواسته انجام نمی‌شود. پاسخ فرم رایگان یک ثبت اطلاعاتی است، نه رسید پرداخت یا تضمین ظرفیت.

پاسخ‌های نهایی تا حذف مالک در پایگاه‌داده باقی می‌مانند؛ انقضای پیش‌نویس یا کوکی به‌تنهایی پاسخ نهایی را حذف نمی‌کند. کوکی قابلیت پیش‌فرض ۳۰ روز اعتبار دارد؛ پس از انقضای آن، پاسخ‌دهنده دیگر از همان مرورگر نمی‌تواند پاسخ قبلی را حذف/ویرایش کند و باید از مالک کمک بگیرد. مالک برای حذف، مسیر اختصاصی API را با نشست و CSRF فراخوانی می‌کند.

دادهٔ پاسخ می‌تواند اطلاعات شخصی داشته باشد و به‌صورت JSON/JSONB ذخیره می‌شود؛ این نسخه رمزگذاری فیلدها در DB را فراهم نمی‌کند. HTTPS، دسترسی محدود DB، رمزگذاری دیسک و backup، برنامهٔ نگه‌داری/حذف داده و پایش دسترسی را در استقرار واقعی تنظیم کنید. limiter فعلی IP اتصال مستقیم FastAPI را HMAC می‌کند و IP خام را ذخیره نمی‌کند؛ پشت proxy چندکاربره، proxy ممکن است همه را یک IP نشان دهد. اعتماد به `X-Forwarded-For` در این برنامه فعال نشده است؛ reverse proxy را آگاهانه پیکربندی کنید و limiter لبهٔ شبکه را هم داشته باشید.

## پیش‌نیاز و تنظیم امن

Python 3.11+، PostgreSQL قابل‌دسترس و بسته‌های `requirements.txt` لازم‌اند. route تصویر/دانلود بلیت از همان renderer در `bale-bot/nora_bot/form_ticket_image.py` استفاده می‌کند؛ این فایل و `bale-bot/nora_bot/jalali.py` باید کنار برنامه باشند و Pillow/qrcode از requirements نصب شوند. اگر renderer در دسترس نباشد، endpoint خطا می‌دهد و هیچ تصویر جایگزین یا ساختگی نمی‌سازد. برای کار محلی از محیط مجازی استفاده کنید:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r website/nora-ui/backend/requirements.txt
.venv/bin/python -m pip install -r website/nora-ui/backend/requirements-dev.txt  # توسعه و آزمون
```

پایگاه‌داده و کاربر PostgreSQL را جداگانه با حداقل مجوز لازم بسازید. URL اتصال، شناسهٔ مالک، نام کاربری و **هش** گذرواژه را در secret manager یا محیط محافظت‌شدهٔ همان میزبان تنظیم کنید. برای Mini App، `NORA_BALE_BOT_TOKEN` را فقط در محیط سرور بگذارید. برای OTP وب، `SAFIR_API_KEY` و `SAFIR_BOT_ID` لازم‌اند؛ `NORA_OTP_PEPPER` جداگانه و پایدار (حداقل ۳۲ نویسهٔ تصادفی) توصیه می‌شود تا digest هویت تلفن با چرخش کلید ارسال تغییر نکند. در نبود pepper، کلید Safir به‌عنوان fallback به‌کار می‌رود. بدون کلیدهای لازم OTP، endpoint با 503 بسته می‌ماند. فایل `.env` نسازید یا آن را از وب منتشر نکنید. هیچ رمز، توکن نشست یا secret را در مرورگر، `localStorage`، HTML یا چت قرار ندهید.

برای تولید هش گذرواژه، خود گذرواژه در ترمینال به‌صورت پنهان خوانده می‌شود:

```bash
.venv/bin/python - <<'PY'
import getpass, sys
sys.path.insert(0, 'website/nora-ui')
from backend.security import hash_password
print(hash_password(getpass.getpass('گذرواژهٔ مالک (حداقل ۱۲ نویسه): ')))
PY
```

هش خروجی را در secret manager به `NORA_OWNER_PASSWORD_HASH` بدهید. متغیرهای پیکربندی:

| متغیر | مقدار/پیش‌فرض |
|---|---|
| `NORA_DATABASE_URL` | برای PostgreSQL از `postgresql+psycopg://…` استفاده کنید؛ `postgres://` و `postgresql://` هم به psycopg 3 تبدیل می‌شوند. |
| `NORA_OWNER_ID`, `NORA_OWNER_USERNAME`, `NORA_OWNER_PASSWORD_HASH` | هویت مالک و هش scrypt؛ مقدارهای محرمانه فقط در محیط سرور. |
| `NORA_BALE_BOT_TOKEN` | اختیاری؛ فقط برای اعتبارسنجی `initData` در endpoint جداگانهٔ Mini App لازم است. OTP پیامکی Safir و ورود گذرواژه‌ای وب به آن نیاز ندارند. فقط در محیط سرور؛ برای پرداخت فرم استفاده نمی‌شود. |
| `NORA_FORM_PAYMENT_BOT_TOKEN` | توکن **ربات اختصاصی پرداخت فرم**؛ با ربات/handler قدیمی اشتراک نگذارید. تا وقتی توکن معتبر این‌جا تنظیم نشود، کیف پول بله غیرفعال می‌ماند. فقط محیط امن backend. |
| `NORA_FORM_PAYMENT_PROVIDER_TOKEN` | provider token صورتحساب بله؛ فقط محیط امن backend، هرگز مرورگر/HTML/چت. |
| `NORA_FORM_PAYMENT_WEBHOOK_SECRET` | راز مستقلِ تصادفی ۳۲ تا ۲۵۶ نویسهٔ ASCII برای ساخت HMAC مسیر webhook؛ توکن مسیر از این راز و bot اختصاصی مشتق می‌شود. به هدر secret نامستندِ provider تکیه نمی‌شود. |
| `NORA_FORM_PAYMENT_WEBHOOK_URL` | نشانی عمومیِ قابل‌دسترسی از اینترنت با TLS معتبر که دقیقاً به `/api/payments/bale/webhook` ختم شود؛ backend توکن HMAC را به مسیر ثبت‌شده اضافه می‌کند. HTTP، localhost، IP خصوصی، دامنهٔ آزمایشی، query، fragment و URL دارای credential رد می‌شوند. |
| `NORA_FORM_PAYMENT_TTL_SECONDS` | انقضای صورتحساب؛ پیش‌فرض ۱۸۰۰، بازهٔ ۶۰ تا ۸۶۴۰۰ ثانیه. |
| `NORA_FORM_PAYMENT_TIMEOUT_SECONDS` | timeout تماس Bot API؛ پیش‌فرض ۸ و حداکثر ۸ ثانیه تا پاسخ `pre_checkout_query` پیش از مهلت بله برگردد. |
| `NORA_FORM_PAYMENT_MAX_AMOUNT` | سقف هر صورتحساب به ریال؛ پیش‌فرض ۲٬۰۰۰٬۰۰۰٬۰۰۰ و بازهٔ ۱ تا همین سقف. |
| `NORA_BALE_BOT_USERNAME` | اختیاری؛ نام کاربری عمومی ربات بله، بدون `@`، برای پیوندهای تحویل بلیت و دسترسی‌های مستقیم بات؛ برای ورود وب لازم نیست. |
| `SAFIR_API_KEY`, `SAFIR_BOT_ID` | فقط برای تحویل OTP شماره با پیامک از API Safir؛ `bot_id` تنظیم سرویس ارسال است، نه شناسهٔ هویت حساب وب یا شناسهٔ کاربر بله. فقط در backend بمانند. |
| `NORA_OTP_PEPPER` | pepper پایدار و محرمانه، حداقل ۳۲ نویسه؛ برای digest کد، شماره و محدودیت‌های OTP. اگر خالی باشد، `SAFIR_API_KEY` fallback است. |
| `SAFIR_URL` | پیش‌فرض `https://safir.bale.ai/api/v3/send_message`؛ فقط HTTPS روی میزبان Safir پذیرفته می‌شود. |
| `SAFIR_SEND_REQUEST_ID` | پیش‌فرض `1`; ارسال request ID در درخواست Safir. |
| `OTP_TTL_MINUTES` | پیش‌فرض ۳، بازهٔ مجاز ۱ تا ۱۵ دقیقه. |
| `OTP_MAX_ATTEMPTS` | پیش‌فرض ۵، بازهٔ مجاز ۱ تا ۱۰ تلاش برای هر کد. |
| `OTP_RESEND_SECONDS` | پیش‌فرض ۹۰، بازهٔ مجاز ۳۰ تا ۶۰۰ ثانیه. علاوه بر آن، محدودیت درخواست بر اساس IP و شماره اعمال می‌شود. |
| `NORA_BOT_SERVICE_TOKEN` | برای وب اختیاری؛ اگر API ربات/claim بلیت استفاده شود، راز مشترک دست‌کم ۳۲ نویسه‌ای لازم است. سرویس مستقل `bale-bot/nora_bot/` نیز برای اتصال به API آن را نیاز دارد؛ فقط در backend و محیط ربات، هرگز مرورگر. |
| `NORA_OWNER_BALE_USER_ID` | برای وب اختیاری؛ برای اجرای بات باید شناسهٔ مالک سرور باشد و با `SUPER_ADMIN_ID` ربات تطبیق کند. نقش همچنان از پیکربندی سرور می‌آید، نه از SQLite. |
| `NORA_BALE_INIT_DATA_MAX_AGE_SECONDS` | پیش‌فرض ۶۰۰ ثانیه؛ بازهٔ مجاز ۶۰ تا ۳۶۰۰ ثانیه. |
| `NORA_COOKIE_SECURE` | پیش‌فرض `1`; فقط آزمایش محلی HTTP می‌تواند `0` باشد. |
| `NORA_COOKIE_SAMESITE` | پیش‌فرض `strict` (تولید همین بماند). `none` فقط برای پیش‌نمایش آزمایشی داخل iframe و فقط همراه `NORA_COOKIE_SECURE=1`؛ مقدار نامعتبر یا `none` بدون کوکی امن → `strict`. |
| `NORA_SESSION_TTL_SECONDS` | پیش‌فرض ۲۸۸۰۰ (۸ ساعت)، بازهٔ مجاز ۹۰۰ تا ۸۶۴۰۰ ثانیه. |
| `NORA_RESPONSE_DRAFT_TTL_SECONDS` | پیش‌فرض ۲۵۹۲۰۰۰ (۳۰ روز)، بازهٔ مجاز ۶۰ ثانیه تا ۳۶۵ روز. پاسخ نهایی با این تنظیم پاک نمی‌شود. |
| `NORA_RESPONSE_DRAFT_WRITE_LIMIT_PER_MINUTE` | پیش‌فرض ۱۲۰ درخواست در دقیقه برای خواندن/ذخیره/پاک‌کردن نشست عمومی؛ بازهٔ مجاز ۱ تا ۱۰۰۰۰. |
| `NORA_RESPONSE_SUBMIT_LIMIT_PER_MINUTE` | پیش‌فرض ۱۰ ثبت نهایی در دقیقه؛ بازهٔ مجاز ۱ تا ۱۰۰۰. |

محدودیت‌ها فعلاً به ازای IP اتصال مستقیم و فرم هستند، نه هویت فرد؛ آن‌ها را ابزار جلوگیری کامل از ربات یا حملهٔ توزیع‌شده تلقی نکنید.

## SEO دامنهٔ عمومی

برای تنظیم دامنهٔ رسمی، `robots.txt`، `sitemap.xml`، metadata صفحات عمومی، JSON-LD و اطلاعات LocalBusiness، فقط از origin و مشخصات تأییدشدهٔ سرور استفاده کنید. راهنمای تنظیم و رفتار fail-closed در [`SEO.md`](../SEO.md) است؛ تا تعیین origin رسمی، sitemap با `503` بسته می‌ماند.

## migration و اجرا

برنامه schema را خودکار تغییر نمی‌دهد. ابتدا همهٔ migrationها را اجرا کنید؛ migrationهای پاسخ عمومی، هویت مشترک، نشست بله و شناسه/claim/ورود بلیت مشترک را هم می‌سازند:

```bash
.venv/bin/alembic -c website/nora-ui/backend/alembic.ini upgrade head
.venv/bin/uvicorn --app-dir website/nora-ui backend.app:app --host 0.0.0.0 --port 8000
```

برای UI و `/api/...` از همان میزبان/مبدأ استفاده کنید. در HTTPS، `NORA_COOKIE_SECURE=1` را حفظ کنید؛ پشت reverse proxy، TLS، محدودیت اندازهٔ درخواست، headerهای host و آدرس client را آگاهانه تنظیم کنید. `/api/health` تا زمان اتصال DB و وجود جدول‌های migrationشده، آمادگی `formsEnabled` و `responsesEnabled` را `false`/503 می‌دهد.

- `0001_initial_forms`: `forms`، `form_fields`، `owner_sessions` و `login_throttles`.
- `0002_public_responses`: `form_response_drafts`، `form_responses` و `public_write_throttles` به‌همراه indexها. PostgreSQL برای مقادیر JSON از `JSONB` استفاده می‌کند.
- `0003_cooperation_requests`: صندوق خصوصی درخواست‌های همکاری.
- `0004_public_site_content`: snapshot محتوای منتشرشدهٔ سایت.
- `0005_shared_accounts`: حساب داخلی و شناسه‌های سکو؛ دادهٔ قدیمی را وارد نمی‌کند.
- `0006_bale_account_sessions`: نشست قابل ابطال و اثرانگشت یک‌بارمصرف `initData`.
- `0007_account_roles`: نقش سروری حساب‌های مشترک؛ فقط `manager` و `club-supervisor` قابل واگذاری‌اند و نقش `owner` به نشست مالک محدود است.
- `0008_shared_workflows`, `0009_workflow_projection`: کارتابل تأیید مشترک و projection ربات.
- `0010_private_files`, `0011_bot_form_history`: پیوست خصوصی، فایل‌های حساب و تاریخچهٔ ربات.
- `0012_shared_form_tickets`, `0013_form_receipt_review_link`, `0014_form_receipt_uploads`: بلیت مشترک و بازبینی رسید.
- `0015_phone_otp_login`: چالش OTP با digest، نوع احراز هویت نشست حساب، و محدودیت تلاش؛ دادهٔ قدیمی نشست‌ها به‌عنوان `bale` مهاجرت می‌کند.
- `0016_manager_password_login`: اعتبارنامهٔ مدیر با نام کاربری یکتا و هش گذرواژهٔ scrypt؛ خودِ گذرواژه به مرورگر یا API فهرست برنمی‌گردد.
- `0017_form_companions`: ذخیرهٔ موقت هویت و پاسخ‌های همراه در پیش‌نویس؛ رکوردهای قدیمی حفظ می‌شوند.
- `0018_separate_companion_responses`: ثبت هر همراه به‌صورت ردیف مستقل پاسخ، همراه با نام/موبایل و نسبت «افزوده‌شده توسط»؛ داده‌های پاسخ‌های قدیمی دست‌نخورده می‌مانند.
- `0019_form_receipt_notes`: یادداشت اختیاری شرکت‌کننده روی رسید ارسالی.
- `0020_form_payments`: intentهای کارت‌به‌کارت/کیف پول، payload فاکتور، مبلغ محاسبه‌شده و وضعیت server-side.
- `0021_form_payment_transactions`: دفتر ثبت یکتای transaction/charge بله برای retry امن و جلوگیری از ثبت دوباره.
- `0022_web_account_registration_history`: پیوند پاسخ‌های عمومی فرم به نشست تأییدشدهٔ حساب وب.
- `0023_payment_secrets`: نگهداری رمزشدهٔ secretهای درگاه پرداخت که مالک وارد می‌کند.
- `0024_account_profiles`: فیلدهای پروفایل عضو در صفحهٔ حساب.
- `0025_service_checks`: ثبت نتیجهٔ آزمون‌های اتصال واقعی سرویس‌ها.
- `0026_admin_audit_events`: تاریخچهٔ افزودنیِ عملیات مدیریتی (بدون secret).
- `0027_ticket_checkin_account`: ثبت حساب پنل وبی که ورود بلیت را زده است.
- `0028_certificates`: آینهٔ گواهی‌های صادرشدهٔ ربات برای پنل مدیران (`certificates`؛ فایل‌ها در `private_files`؛ مالک فقط از `platform_identities`). افزودنی و برگشت‌پذیر.
- `0029_public_media`: تصاویر عمومی بارگذاری‌شده از پنل (`public_media`؛ URL پایدار `/api/public/media/{id}` در `site_content`). افزودنی و برگشت‌پذیر.
- `0030_club_points_entries`: آینهٔ فقط‌خواندنی دفترکل امتیاز ربات (`club_points_entries`؛ کلید پایدار `external_key = <source_id>:<ledger_id>`؛ فقط ردیف‌های کاربران با هویت بلهٔ پیوندشده). نوشتن فقط از `POST /api/bot/club/points` با توکن سرویس ربات؛ پنل فقط می‌خواند (`GET /api/admin/club/points…` با مجوز `cl_member`). هیچ امتیازی سمت سرور ساخته/خرج نمی‌شود. افزودنی و برگشت‌پذیر.

پیوند عمومی در `create.html` پس از انتشار نشان داده می‌شود و به `form.html?fid=<شناسه>&kind=<نوع>` می‌رود. از افزودن `preview=1` به پیوند عمومی خودداری کنید؛ آن پارامتر عمداً پیش‌نمایش محلی سازنده را باز می‌کند.

## مسیرهای API

| مسیر | دسترسی و رفتار |
|---|---|
| `GET /api/health` | اتصال DB و آماده‌بودن فرم/پاسخ را گزارش می‌کند؛ `formBalePaymentsReady` فقط با bot اختصاصی معتبر، provider token، راز webhook، URL عمومی HTTPS و timeout امن `true` می‌شود. در پیکربندی پیش‌فرض پرداخت بله خاموش است. صف پیام/اعلان عمومی خاموش است و فقط endpoint OTP می‌تواند Safir را فراخوانی کند. |
| `GET /api/public/site-content` | snapshot عمومیِ منتشرشده؛ پیش از اولین انتشار 404 می‌دهد. سایت در حالت تولیدی محتوای محلی/نمونه را جایگزین نمی‌کند و صفحه را خالی یا unavailable نشان می‌دهد؛ fixture محلی فقط با `__NORA_TEST_FIXTURE_MODE__` صریح در آزمون فعال می‌شود. |
| (فاز ۷) زمان و وضعیت رویداد | رکورد رویداد در `site_content` فیلدهای اختیاری `startsAt/endsAt/regOpensAt/regClosesAt` (ISO‑8601 UTC؛ پنل می‌تواند شمسی‑تهران بفرستد)، `regMode ∈ {auto,closed,full}`, `lifecycle ∈ {scheduled,cancelled,postponed}`, `conditions` دارد. خروجی عمومی برای هر رویداد `registration{state, reason, opensAt, closesAt, countdownTo, …}` و در ریشه `server_time` می‌دهد؛ وضعیت ثبت‌نام **سمت سرور** و جدا از وضعیت انتشار محاسبه می‌شود (`event_time.py`). APIهای فرم (`GET /api/public/forms/{id}`, `/draft`, `/responses`, `/payment-intents`) برای رویدادِ باز‑نبوده `409 {code: registration_closed, state}` می‌دهند. بنر می‌تواند با `eventId` به رویداد وصل شود (`countdown ∈ {reg_close, event_start, campaign_end}`, `afterEnd ∈ {hide, message, details}`)؛ زمان بنرِ وصل‌شده از رویداد خوانده می‌شود و در بنر ذخیره نمی‌شود. بدون مهاجرت DB. |
| `GET /api/owner/site-content`, `PATCH /api/owner/site-content` | خواندن و همگام‌سازی دسته‌های انتخاب‌شدهٔ محتوای عمومی؛ نشست مالک، CSRF و نسخهٔ مورد انتظار لازم است. هر دستهٔ ارسالی جایگزین همان دسته می‌شود. |
| `POST /api/auth/staff-login` | endpoint فرم مشترک مدیر/مالک؛ backend اعتبارنامه را با تنظیمات مالک یا اعتبارنامهٔ مدیرِ واگذارشده تطبیق می‌دهد و نشست سروری متناظر (`owner` یا `manager-password`) می‌سازد. خطای عمومی، محدودیت تلاش، کوکی‌های `HttpOnly` و هم‌مبدأ؛ نقش از body پذیرفته نمی‌شود. |
| `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` | endpoint اختصاصی نشست مالک؛ ورود هم‌مبدأ، logout با CSRF. |
| `POST /api/auth/manager-login` | endpoint اختصاصی نام‌کاربری/گذرواژهٔ مدیر؛ اعتبارنامهٔ scrypt، محدودیت تلاش بر پایهٔ IP و نام کاربری، پیام خطای عمومی، نشست کوکی `HttpOnly` با provider=`manager-password`. فقط حسابِ ازپیش‌نقش‌گرفته؛ ورود هیچ نقشی اعطا نمی‌کند. |
| `POST /api/auth/bale-mini-app` | تأیید امضای `initData`، تازگی و عدم replay؛ کوکی نشست حساب با provider=`bale`. فقط هم‌مبدأ و نیازمند `NORA_BALE_BOT_TOKEN`. |
| `POST /api/auth/phone-otp/request` | نرمال‌سازی شمارهٔ ایران، محدودیت IP/شماره/ارسال مجدد، ساخت چالش تصادفی و تحویل OTP از Safir؛ کد/شماره به مرورگر برگردانده نمی‌شود. فقط هم‌مبدأ و نیازمند تنظیم Safir. |
| `POST /api/auth/phone-otp/verify` | بررسی digest کد، شماره، انقضا و تعداد تلاش؛ چالش فقط یک‌بار مصرف و سپس نشست حساب provider=`phone` ساخته می‌شود. نقش فقط از `account_roles` خوانده می‌شود. پاسخ موفق علاوه بر `account_id`، دو پرچم `created` (هویت این شماره پیش از همین کد وجود نداشت) و `profile_saved` (ردیف `account_profiles` دارد) را برمی‌گرداند؛ هر دو فقط پس از اثبات کد تعیین می‌شوند و صفحهٔ ورود با آن‌ها «حساب تازه» را از «عضو قدیمی» تشخیص می‌دهد. |
| `GET /api/account/me`, `POST /api/auth/account/logout` | هویت، provider، نقش و مجوزهای نشست بله، OTP یا گذرواژهٔ مدیر؛ خروج با CSRF. نقش از پایگاه‌داده می‌آید، نه مرورگر. |
| `POST /api/bot/identity` | دریافت نقش و مجوزهای یک شناسهٔ بله برای ربات؛ فقط با Bearer token سروری، بدون CSRF مرورگر، و تا زمان پیکربندی راز سرویس با 503 بسته است. |
| `GET /api/bot/forms/public`, `POST /api/bot/forms/{id}/draft`, `POST /api/bot/forms/{id}/draft/state`, `PATCH /api/bot/forms/{id}/draft`, `DELETE /api/bot/forms/{id}/draft`, `POST /api/bot/forms/{id}/responses` | گفتگوی فرم‌های منتشرشدهٔ بدون همراه؛ فرم‌های همراه‌دار در فهرست ربات نمی‌آیند و مسیرهای نوشتن مستقیم برای آن‌ها بسته‌اند. Bearer سرویس و شناسهٔ بله در بدنه لازم‌اند. حذف فقط پیش‌نویس را پاک می‌کند و پاسخ نهایی را نگه می‌دارد. |
| `GET /api/bot/forms/mine`, `GET /api/bot/forms/responses/{response_id}` | تاریخچه و جزئیات فقط برای صاحب پاسخ؛ Bearer سرویس، شناسهٔ بله، کنترل مالکیت سمت سرور و `Cache-Control: no-store`. |
| `POST /api/bot/forms/{form_id}/responses/{response_id}/ticket` | دریافت بلیت ثبت‌نام پذیرفته‌شدهٔ همان حساب از DB مشترک، همراه با مدل اختصاص‌یافته؛ Bearer سرویس و کنترل مالکیت. |
| `POST /api/bot/form-tickets/claim` | اتصال پیوند صفحهٔ وب به شناسهٔ حساب بله؛ توکن امضاشده و Bearer سرویس لازم است. برای کارت‌به‌کارت، پیش از `paid_manual` فقط task بازبینی ساخته می‌شود و پاسخ `ticket_payment_not_confirmed` می‌گیرد؛ همان claim پس از تأیید دستی بلیت واقعی را می‌دهد. |
| `POST /api/bot/form-tickets/{response_id}/verify`, `POST /api/bot/form-tickets/{response_id}/check-in` | بررسی و ثبت ورود بلیت؛ Bearer سرویس و مجوز سروری `fm_responses`. |
| `GET /api/bot/admin/forms`, `GET /api/bot/admin/forms/{form_id}/responses`, `GET /api/bot/admin/responses/{response_id}` | فهرست و جزئیات صفحه‌بندی‌شدهٔ پاسخ‌های مشترک؛ توکن سرویس و مجوز سروری `fm_responses` برای همان شناسهٔ بله الزامی است؛ پاسخ‌ها `Cache-Control: no-store` دارند. |
| `GET /api/account/files`, `GET /api/account/files/{file_id}` | فهرست فقط metadata می‌دهد؛ دریافت از حساب وب با 410 به بات بله هدایت می‌شود. |
| `GET /api/admin/reports/summary?period=7d|30d|90d|365d|all` | گزارش تجمیعیِ بدون پاسخ شخصی یا مبلغ پرداخت؛ نشست مالک یا نشست `manager-password` با مجوز سروری `rp_view`. نشست OTP به‌تنهایی پذیرفته نمی‌شود. |
| `GET /api/admin/inbox` | کارتابل مشترک؛ نشست مالک یا نشست گذرواژه‌ای مدیر با مجوز کارتابل لازم است. |
| `POST /api/bot/reports/summary` | نسخهٔ ربات از همان گزارش تجمیعی؛ Bearer سرویس و شناسهٔ بله در بدنه لازم است و مجوز `rp_view` برای همان حساب دوباره از پایگاه سنجیده می‌شود. پاسخ فقط آمار و بدون مبلغ/هویت فردی است. |
| `GET /api/admin/inbox/{task_id}/files/{file_id}` | پیوست همان کارتابل برای بررسی مدیر/سرپرست باقی می‌ماند؛ مجوز نوع درخواست و مالکیت پیوست بررسی می‌شود. |
| `GET /api/bot/files`, `GET /api/bot/files/{file_id}`, `GET /api/bot/content-files/{delivery_id}` | فهرست/دریافت پیوست حساب و فایل منتشرشده فقط برای توکن سرویس بات؛ دریافت کاربر از مسیر خصوصی بله انجام می‌شود. |
| `GET /api/owner/accounts` | فهرست صفحه‌بندی‌شدهٔ حساب‌های تأییدشده با بله یا OTP، نقش و نام کاربریِ مدیرِ پیکربندی‌شده؛ شماره در شناسهٔ OTP خام ذخیره/نمایش داده نمی‌شود و هش گذرواژه هرگز برنمی‌گردد؛ فقط نشست مالک. |
| `PUT /api/owner/accounts/{account_id}/role` | واگذاری یا برداشتن نقش مدیر/سرپرست باشگاه؛ فقط نشست مالک، هم‌مبدأ و CSRFدار. برداشتن نقش اعتبارنامه و نشست‌های مدیر را لغو می‌کند؛ نقش مالک از این مسیر قابل واگذاری نیست. |
| `PUT /api/owner/accounts/{account_id}/manager-credentials`, `DELETE /api/owner/accounts/{account_id}/manager-credentials` | تعیین/بازنشانی یا حذف اعتبارنامهٔ حساب دارای نقش مدیر/سرپرست؛ username/password در بدنهٔ HTTPS و فقط با نشست مالک و CSRF. گذرواژه حداقل ۱۲ بایت UTF-8 است، با scrypt هش می‌شود و تغییر/حذف، نشست‌های قبلی مدیر را می‌بندد. |
| `GET /api/forms` | فهرست فرم‌های همان سامانه؛ مالک یا نشست `manager-password` دارای نقش سروری با `fm_create`. OTP عضو برای API مدیریتی وب کافی نیست. |
| `POST /api/forms` | ایجاد `draft` با `Idempotency-Key`؛ مالک یا نشست `manager-password` با نقش `fm_create`، هم‌مبدأ و CSRF همان نشست. |
| `GET /api/forms/{id}`, `PUT /api/forms/{id}` | خواندن/ویرایش با مجوز سروری `fm_create`؛ مدیر باید نشست `manager-password` داشته باشد و ویرایش با CSRF و `expected_version` انجام می‌شود. |
| `POST /api/forms/{id}/publish`, `POST /api/forms/{id}/pause` | انتشار/توقف فقط با نشست مالک، CSRF و نسخهٔ مورد انتظار. |
| `GET /api/public/forms/{id}` | تعریف عمومی فرم منتشرشده، قیمت‌ها و فقط روش‌های انتخاب‌شدهٔ همان فرم؛ کیف پول بله فقط با backend امن آماده در پاسخ می‌آید. وقتی ظرفیت/صف پر است 410. |
| `POST /api/public/forms/{id}/payment-intents` | ساخت/بازیابی صورتحساب pending کیف پول بله برای نشست همان فرم؛ قیمت و انتخاب در سرور دوباره محاسبه می‌شوند. پاسخ فقط پیوند صورتحساب است؛ پاسخ فرم یا پرداخت موفق در مرورگر ساخته نمی‌شود. درخواست تکراری با انتخاب یکسان همان intent را برمی‌گرداند. |
| `GET /api/public/forms/{id}/payment-intents/{payment_id}`, `DELETE /api/public/forms/{id}/payment-intents/{payment_id}` | خواندن وضعیت intent متعلق به همان نشست یا لغو intent pending؛ وضعیت نهایی فقط از webhook سرور می‌آید. |
| `POST /api/payments/bale/webhook/{token}` | webhook مستقل همین FastAPI با توکن مسیر HMAC‌شده؛ `pre_checkout_query` را سریع پاسخ می‌دهد و `successful_payment` را با `inquireTransaction`، مبلغ، ارز، payer و charge در backend تطبیق می‌دهد. جدول `form_payment_transactions` retry و charge تکراری را idempotent می‌کند. مسیر به webhook/SQLite handler بات قدیمی متکی نیست. |
| `GET /api/public/forms/{id}/draft` | ایجاد یا بازیابی نشست ناشناس و کوکی قابلیت مختص فرم؛ بدون پروفایل. `answers` و همراهان برمی‌گردند؛ پس از ثبت، همراهان از ردیف‌های مستقل پاسخ بازیابی می‌شوند. |
| `PATCH /api/public/forms/{id}/draft` | اعتبارسنجی و autosave پاسخ ناقص؛ فقط هم‌مبدأ. بدنه `{ "answers": { ... }, "companions": [{ "name": "...", "mobile": "...", "answers": { "field_id": "..." } }] }` است؛ `companions` فقط در پیش‌نویس گروهی‌اند. |
| `POST /api/public/forms/{id}/responses` | اعتبارسنجی کامل و ثبت پاسخ اصلی و هر همراه به‌صورت ردیف مستقل؛ کارت‌به‌کارت فقط با روش فعال و مبلغ محاسبه‌شدهٔ سرور ثبت می‌شود و به `awaiting_receipt` می‌رود. پرداخت بله از این endpoint تأیید نمی‌شود؛ فقط webhook پس از استعلام provider می‌تواند پاسخ `accepted` بسازد. |
| `POST /api/public/forms/{id}/receipt` | بارگذاری رسید کارت‌به‌کارت به نشست پاسخ؛ آپلود به‌تنهایی پرداخت را تأیید نمی‌کند و ticket image را باز نمی‌کند. claim لینک بله، رسید را به task بازبینی مشترک سمت سرور می‌سپارد. |
| `GET /api/public/forms/{id}/ticket-image` | تصویر واقعی renderer مشترک از پاسخ ثبت‌شده و نامِ واردشده در پاسخ؛ `no-store` و فقط پس از پرداخت تأییدشده (`paid`/`paid_manual`) و هر رسید لازم. صف انتظار، نشست دیگر یا پرداخت بررسی‌نشده تصویر نمی‌گیرد. |
| `POST /api/public/forms/{id}/ticket-link` | پیوند opaque به بات؛ پس از تأیید پرداخت بلیت را تحویل می‌دهد. برای کارت‌به‌کارتِ رسیددار، پیش از تأیید دستی فقط claim/review را آغاز می‌کند و بلیت واقعی را افشا نمی‌کند. |
| `DELETE /api/public/forms/{id}/draft` | پاک‌کردن نشست و پاسخ وابسته با کوکی همان مرورگر؛ فقط هم‌مبدأ. |
| `GET /api/forms/{id}/responses` | فهرست مستقل پاسخ هر نفر با مجوز `fm_responses`؛ ردیف همراه، نام/موبایل و «افزوده‌شده توسط» دارد. pagination حداکثر ۱۰۰ نفر. |
| `DELETE /api/forms/{id}/responses/{response_id}` | حذف پاسخ فقط برای مالک و با CSRF. |
| `GET /api/integrations/status`, `POST /api/outbox` | سیاست اتصال خاموش؛ پیام/صفی ایجاد یا ارسال نمی‌شود. |
| `GET /api/public/events/{id}/interaction` | (فاز ۸) نمای تعامل یک رویداد منتشرشده: منابع با وضعیت دسترسیِ همین بیننده (`allowed`/`reason`)، پرسش‌های منتشرشده + پرسش‌های در انتظارِ خودِ کاربر، دیدگاه‌های منتشرشده و دیدگاه خود کاربر، وضعیت باز/بستهٔ پرسش‌وپاسخ و `server_time`. منابع `staff`/حذف‌شده/زمان‌بندی‌نشده برای غیرکارکنان دیده نمی‌شود. |
| `GET /api/public/events/{id}/resources/{rid}/download` | (فاز ۸) دانلود فقط پس از بررسی سمت سرور: رویداد منتشر، منبع منتشر و `publish_at ≤ now`، سطح دسترسی `public` / `registered` (پاسخ پذیرفته‌شده با پرداخت تأییدشده در فرم همین رویداد) / `attended` (`ticket_checked_in_at`) / `staff`. ۴۰۱ بدون نشست، ۴۰۳ با `detail.reason`، ۴۰۴ برای شناسهٔ ناشناخته؛ `Content-Disposition` + `nosniff` + `no-store`. |
| `POST /api/account/events/{id}/questions`, `POST …/questions/{qid}/report` | (فاز ۸) پرسش فقط با نشست حساب (هویت از سرور)، حداکثر ۱۰۰۰ نویسه، ضدتکرار (۴۰۹) و ۵ پرسش در ساعت (۴۲۹)؛ `qaClosed` یا رویداد لغوشده → ۴۰۹ `qa_closed`. گزارش فقط برای محتوای قابل‌مشاهده. |
| `POST /api/account/events/{id}/reviews`, `PUT …/reviews/{rid}`, `POST …/reviews/{rid}/withdraw`, `POST …/reviews/{rid}/report` | (فاز ۸) دیدگاه فقط برای حضور تأییدشده (۴۰۳ `review_not_eligible`)، یک دیدگاه برای هر حساب/رویداد، بدون امتیاز عددی؛ ویرایش/انصراف خود کاربر بدون پاک‌شدن ردیف ممیزی. |
| `GET/POST /api/admin/events/{id}/resources`, `PUT …/{rid}`, `PUT …/{rid}/file`, `POST …/{rid}/remove` | (فاز ۸) مدیریت منابع با `ev_create`: فایل (نوع/حجم/نام بررسی می‌شود، حداکثر ۸ مگابایت، بایت‌ها در DB) یا پیوند، زمان انتشار، سطح دسترسی، جایگزینی فایل، حذف منطقی با دلیل؛ همه با ردیف ممیزی. |
| `GET /api/admin/events/{id}/questions`, `GET /api/admin/event-questions?answered=false`, `POST …/questions/{qid}/answer`, `POST …/questions/{qid}/status`, `POST …/questions/{qid}/resend-notification` | (فاز ۸) خواندن با `ev_create`/`ev_publish`؛ پاسخ، رسمی‌کردن، انتشار/پنهان‌سازی (پنهان‌سازی نیازمند دلیل) و ارسال دوبارهٔ اعلان فقط با `ev_publish`. پاسخ مستقل از نتیجهٔ اعلان ذخیره می‌شود. |
| `GET /api/admin/events/{id}/reviews`, `POST …/reviews/{rid}/status`, `GET /api/admin/event-reports`, `POST /api/admin/event-reports/{id}/resolve`, `GET /api/admin/event-interaction/summary` | (فاز ۸) دیدگاه‌ها و گزارش‌های محتوا به تفکیک رویداد + خلاصهٔ بین‌رویدادی (بی‌پاسخ، در انتظار، گزارش باز) برای داشبورد؛ تغییر وضعیت با دلیل و بازیگر ممیزی می‌شود. |
| `GET /api/public/recordings`, `GET /api/public/events/{id}/recording` | (فاز ۹) فهرست محصول‌های ضبط‌شدهٔ `published`/`sales_paused` (کاور، عنوان، مدرس، قیمت، تعداد جلسه، مدت فقط اگر همهٔ جلسه‌ها مدت دارند) و نمای کامل محصول یک رویداد: جلسه‌ها و منابع منتشرشده، وضعیت دسترسی همین بیننده (`viewer.access`) و **تنها CTA سروری** (`viewer.cta.kind` = `login/free/buy/order_open/view/off_sale/staff_preview/unavailable`). پیش‌نویس برای غیرکارکنان ۴۰۴. هیچ شمارندهٔ خریدار/محبوبیت/تخفیف برنمی‌گردد. |
| `GET /api/public/events/{id}/resources/{rid}/download` (گسترش) | (فاز ۹) سطح دسترسی `purchased`: فقط با ردیف فعال `recording_access` (خرید/رایگان/اعطایی/شرکت‌کننده در صورت `attendee_access`) یا کارکنان؛ ۴۰۳ `purchase_required`/`access_expired`/`access_revoked` با ردیف ممیزی. `delivery=view` → پاسخ inline با `Accept-Ranges`/۲۰۶/۴۱۶ برای پخش در مرورگر، بدون ادعای DRM. |
| `POST /api/account/recordings/{id}/claim`, `POST …/{id}/orders {method}`, `PUT /api/account/recording-orders/{oid}/receipt`, `POST …/{oid}/cancel`, `GET /api/account/recording-orders`, `GET …/{oid}`, `GET /api/account/recordings` | (فاز ۹) دریافت رایگان بدون ردیف سفارش (محصول پولی → ۴۰۹ `recording_not_free`)؛ سفارش با مبلغ/ارز از **سرور** و `Idempotency-Key` (تکرار → همان سفارش)؛ `card_transfer` → `awaiting_receipt` و رسید (JPG/PNG/WebP/PDF ≤ ۸MB) فقط وضعیت را `receipt_submitted` می‌کند و **هرگز دسترسی نمی‌سازد**؛ `bale_wallet` فقط با هویت بلهٔ پیوندخورده (۴۰۹ `bale_identity_required`) و کیف پول پیکربندی‌شده (۵۰۳). کتابخانهٔ حساب فقط ردیف‌های دسترسی واقعی با `expires_at` سرور و `progress: null` (دادهٔ پیشرفت وجود ندارد). |
| وب‌هوک بله (گسترش): پیشوند `norac_` | (فاز ۹) `pre_checkout_query` با مبلغ/ارز/کاربر ناهمخوان رد می‌شود؛ `successful_payment` تنها پس از `inquireTransaction` موفق → `paid` + دسترسی در یک تراکنش، در غیر این صورت `needs_review`؛ تکرار رویداد → یک دسترسی (idempotent). URL موفقیت هیچ نقشی در اعطای دسترسی ندارد. |
| `GET/PUT /api/admin/events/{id}/recording`, `POST …/recording/status`, `GET/POST …/recording/sessions`, `PUT/DELETE …/sessions/{sid}`, `GET/POST …/recording/access`, `POST …/access/{aid}/revoke` | (فاز ۹) محصول/جلسه با `ev_create`؛ وضعیت، اعطا و لغو دسترسی با `ev_publish`. انتشار فقط با `publish_blockers` خالی (رویداد برگزارشده، حداقل یک جلسهٔ منتشرشده با منبع، قیمت/شرایط معتبر)؛ تغییر قیمت با سفارش باز → ۴۰۹ `open_orders_block_price_change`؛ `expected_version` → ۴۰۹ `version_conflict`؛ حذف جلسهٔ دارای فایل → ۴۰۹ `session_has_resources`؛ توقف/بایگانی/لغو دسترسی نیازمند دلیل (۴۲۲). همه با actor در ممیزی. |
| `GET /api/admin/recording-orders?status&event_id&q&format=csv`, `GET …/{oid}`, `GET …/{oid}/receipt`, `POST …/{oid}/decision {decision, reason}`, `POST …/{oid}/refund {reference, reason}`, `GET /api/admin/recordings/summary` | (فاز ۹) خواندن صف با `receipt_approve`/`ev_publish`/`finance`؛ تصمیم (`approve` → `paid_manual` + دسترسی، `reject` → بدون دسترسی + اعلان) فقط با `receipt_approve` و دلیل؛ بازپرداخت و خروجی CSV فقط با `finance` (مالک) و شمارهٔ پیگیری واقعی: `refunded` + دسترسی `revoked` در یک تراکنش. تاریخچهٔ هر سفارش از ردیف‌های ممیزی؛ خلاصهٔ داشبورد صرفاً شمارش ردیف‌های DB. |
| اعلان‌های محتوا (همان صندوق خروجی) | (فاز ۹) `recording_access` هنگام اعطای دسترسی، `recording_order` هنگام رد/بازپرداخت؛ `delivery_status` = `pending` فقط اگر حساب هویت بلهٔ تأییدشده دارد، وگرنه `failed/no_bale_identity`. ثبت ≠ تحویل. |

## آزمون و وضعیت استقرار

چک‌لیست اجرای staging ایزوله، مرور دستی دسترس‌پذیری و محدودیت‌های این آزمون در [راهنمای فرم‌ساز](../FORM-BUILDER-STAGING.md) ثبت شده است؛ نتیجهٔ JSDOM/SQLite به‌تنهایی آمادگی production را ثابت نمی‌کند.

```bash
PYTHONPATH=website/nora-ui .venv/bin/python -m pytest -q website/nora-ui/backend/tests
node --max-old-space-size=3072 website/nora-ui/smoke.test.mjs
node website/nora-ui/login.test.mjs
```

تست‌های API با SQLite موقت، نشست مالک، CSRF، انتشار/توقف فرم و محتوا، نسخه‌بندی، اعتبارسنجی، پاسخ ناشناس، autosave، بازیابی همراهان و ثبت هر همراه در ردیف مستقل با یادداشت ثبت‌کننده، منع دسترسی مسیر نوشتن ربات به فرم همراه‌دار، ظرفیت/صف انتظار، claim یک‌بارمصرف بلیت، مالکیت، جلوگیری از replay، ثبت ورود، حذف و XSS bootstrap را می‌سنجند. آزمون پرداخت نیز آماده‌بودن fail-closed، invoice و webhook مستقل، pre-checkout، استعلام server-side، عدم پذیرش تراکنش pending/ناهمخوان، و idempotency رویداد و charge تکراری را پوشش می‌دهد. آزمون دودی JavaScript در JSDOM همراه‌پرسش، پیش‌نویس/ثبت سروری و نمایش پاسخ برای مدیر را پوشش می‌دهد؛ این تست‌ها جای آزمون مرورگری روی PostgreSQL واقعی را نمی‌گیرند. آزمون ورود مدیر نیز واگذاری مالک‌محور اعتبارنامه، محدودیت تلاش، هش scrypt، برداشت نقش، ابطال نشست، و جلوگیری از دسترسی مدیریتی با OTP را می‌سنجد. تست migration هم upgrade/downgrade را روی SQLite اجرا می‌کند. آزمون UI دودی مسیر ورود OTP و فرم مشترک مالک/مدیر را با API mock پوشش می‌دهد؛ این تست‌ها جای آزمون مرورگری روی PostgreSQL واقعی را نمی‌گیرند.

در محیط فعلی migration و routeها روی SQLite آزموده شده‌اند؛ اتصال PostgreSQL واقعی، TLS/reverse proxy، backup و استقرار production اینجا قابل اثبات نیستند. بنابراین این تغییرات مسیر عملیاتی سروری را پیاده می‌کنند، اما **گواهی آمادگی production نیستند**؛ پیش از استفادهٔ عمومی، migration و آزمون پذیرش را روی PostgreSQL و میزبان استقرار اجرا کنید.
�د.
