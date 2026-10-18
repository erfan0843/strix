# گزارش تکمیلی: اتصال واقعی مدیریت نهادهای همکار به سرور — ۱۴۰۵/۰۷/۲۶ (2026-10-18)

- مخزن `erfan0843/strix` — شاخه `arena/840de336-strix` — PR #1 **باز و ادغام‌نشده** (هیچ merge/deploy/release انجام نشده).
- نقطهٔ شروع: `321c86b` (پایان گزارش `PARTNER-PAGES-AUDIT-2026-10-18.fa.md`). کامیت‌های این مرحله: `3faae21` (قابلیت) + کامیت «تست/گزارش/شواهد» (هش در بخش ۹).
- محیط آزمون: سرور تست ایزوله (`/tmp/nora-preview`, SQLite موقت)، فقط دادهٔ «(دادهٔ تست)». هیچ دادهٔ واقعی تغییر نکرد؛ هیچ رازی در شواهد نیست (رمز مالکِ محیط تست از فایل خارج از مخزن خوانده می‌شود).

---

## ۱. ممیزی اولیه — چرا مدیریت تولید به سرور وصل نبود

مسیر داده (روی کد واقعی دنبال شد):

| لایه | وضعیت قبل |
|---|---|
| `admin.js` → `ppPartnerView()/ppPartnerList()/ppPartnerForm()` (کاشی «مدیران و اساتید ← نهادهای همکار») | ویرایشگر کامل، ولی فقط روی `localStorage` (`S.pp.partnerAdd/partnerO/partnerHide/partnerOrd`) و `ppPub('nora-partners')`. |
| `ppPartnerClean()` / `ppPartnerPublishList()` | خروجی تمیز با `status:'published', pub:true` — فقط به `localStorage` می‌رفت. |
| `renderBody()` در تولید (`!IS_TEST`) | `body()` → `serverBody()` → `serverSettingsView()`؛ یعنی `vSettings()` و کاشی «مدیران و اساتید» **در تولید اصلاً رندر نمی‌شد**. پیوند `admin.html#partners` هم route نداشت. |
| `site-content-sync.js` | `publishedPartners()` در تولید `[]` برمی‌گرداند و چک‌باکس «نهادهای همکار» غیرفعال است («تا اتصال ویرایشگر سروری غیرفعال است»). |
| `GET/PATCH /api/owner/site-content` | کامل و امن (نشست مالک، CSRF، `expected_version` → 409، به‌روزرسانی جزئیِ دسته‌ها). فقط از اسکریپت/بنرها استفاده می‌شد. |
| `backend/site_content.py::_partner` | از مرحلهٔ قبل: مرز انتشار + فیلدهای `s,collab,since,focus,links`. |
| `partner.html` / `partner-page.js` | فقط snapshot عمومی سرور را می‌خواند. |

**نتیجهٔ تأییدشده:** در تولید هیچ مسیر UI برای نهادها وجود نداشت؛ تنها راه، PATCH خام API مالک بود. علت: رابط نهادها فقط در شاخهٔ fixture رندر می‌شد و همگام‌سازی محلی عمداً برای جلوگیری از انتشار دادهٔ مرورگر خاموش بود.

## ۲. اصلاح (همان مسیر موجود؛ بدون پنل دوم، بدون endpoint/جدول/migration)

فایل‌های تغییرکرده (کامیت `3faae21`): `admin.js`, `admin.html`, `site-content-sync.js`, `admin.test.mjs` (پین).

- **همان `ppPartnerView()`** در تولید داخل «تنظیمات ← محتوای عمومی و همکاری» (کنار مدیر بنر و همگام‌سازی) رندر می‌شود؛ `admin.html#partners` و `hashchange` به همان‌جا می‌روند. در حالت fixture رفتار قبلی حفظ شده است.
- **منبع داده در تولید فقط سرور:** `PP_SRV` (غیرپایدار، در حافظهٔ صفحه) با `GET /api/owner/site-content` پر می‌شود؛ `ppPartnerAll()/Merged()/Hidden()` در تولید هیچ لایهٔ `localStorage` یا `data.js` را اعمال نمی‌کنند. فهرست فقط پس از پاسخ موفق سرور نمایش داده می‌شود؛ در خطا، فهرست خالی + پیام + دکمهٔ «تازه‌سازی از سرور».
- **ذخیره:** هر افزودن/ویرایش/حذف/جابه‌جایی → `ppPartnerCommit(list)` → `NORA_SERVER_API.updateSiteContent({partners:list}, PP_SRV.version)` (کوکی نشست + `X-CSRF-Token` از `owner-api.js`). بدنه فقط `content.partners` + `expected_version`؛ رویداد/مطلب/پروفایل/بنر/کتابخانه/فرم همکاری ارسال نمی‌شوند و سرور هم فقط دستهٔ ارسالی را جایگزین می‌کند. نسخه و فهرست از پاسخ سرور بازنویسی می‌شوند.
- **پیام موفقیت** فقط بعد از 2xx؛ ویرایشگر فقط در موفقیت بسته می‌شود. پیش‌نویس فرم تا آن لحظه صریحاً «پیش‌نویس در این مرورگر» معرفی می‌شود.
- **409:** پیام تعارض، بازخوانی فهرست سرور (`keepMessage`)، پیش‌نویس مالک باز می‌ماند تا روی نسخهٔ تازه دوباره ذخیره کند؛ تغییر شخص دیگر حذف نمی‌شود. **401/403/404/413/422/503/5xx/قطع شبکه:** پیام مشخص، هیچ‌چیز «ذخیره‌شده» نشان داده نمی‌شود.
- **حذف** با `confirm` صریح (متن: حذف از فهرست عمومی، از دسترس خارج شدن صفحهٔ اختصاصی، دست‌نخوردن رویدادها).
- **کنترل‌های محلی** («انتشار در مرورگر»، «پنهان/نمایش دوباره»، «بازگشت به دادهٔ سامانه») در تولید رندر نمی‌شوند؛ «رونوشت» در تولید فقط یک پیش‌نویس تازه باز می‌کند (نوشتن فقط با ذخیرهٔ صریح).
- متن راهنما صریح می‌گوید فقط فهرست منتشرشده مدیریت می‌شود و «پیش‌نویس/توقف» روی سرور پشتیبانی نمی‌شود (وعدهٔ قابلیت ذخیره‌نشده داده نمی‌شود).
- `eventPartnerRows()` ویزارد رویداد در تولید فهرست سرور را (lazy) بار می‌کند؛ قبلاً نهادهای نمونهٔ `data.js` را نشان می‌داد.
- `ppPartnerLogo` نشانی protocol-relative (`//host/…`) را مثل سرور رد می‌کند تا به‌جای حذف بی‌صدا در سرور، همان لحظه پیام بدهد.
- `site-content-sync.js`/`admin.html`: متن چک‌باکس و توضیح بخش انتشار به مدیر سروری نهادها ارجاع می‌دهد.

### فیلدهای قابل مدیریت (همان مدل/پاک‌ساز موجود)
`id` (پایدار؛ تازه: `org<timestamp>`)، `n`، `type`، `s` (خلاصه)، `d` (شرح)، `logo` (فایل→data:image یا مسیر امن/https بدون اعتبارنامه) + `mon` و `g`، `href` (وبگاه؛ `http/https` بدون اعتبارنامه)، `collab`، `since`، `focus[]`، `links[]` با انواع `tel/mail/tg/ig/web` (نوع `other` و `javascript:`/`//host` توسط سرور حذف می‌شوند؛ کلاینت هم قبل از ارسال رد می‌کند). هیچ فیلد جدیدی به سرور اضافه نشد.

## ۳. مسیر واقعی ذخیره‌سازی

`admin.html#partners` → `ppPartnerServerLoad()` → `GET /api/owner/site-content` (require_owner) → `PP_SRV.rows/version` → ویرایش در فرم (پیش‌نویس مرورگر) → `ppPartnerCommit()` → `PATCH /api/owner/site-content {content:{partners:[…]}, expected_version}` (require_owner_write + CSRF) → `sanitize_site_content(partial=True)` → `_partner()` (مرز انتشار/allowlist) → `SiteContentRecord.public.version+1` → پاسخ `owner_view` → UI. مصرف‌کننده‌ها: `GET /api/public/site-content` → `home.html` (`#logoWall`, پاورقی)، `partner.html?id=` (+ SEO سرور)، `sitemap.xml`.

## ۴. آزمون‌ها — جدا به تفکیک «سرور واقعی» و «mock»

### ۴-الف. سرور واقعی (Playwright + Chromium، سرور تست محلی، ورود از طریق خودِ `login.html?mode=staff`) — `evidence-partner-management-2026-10-18/tools/partner-manage-verify.mjs` → **۲۵ قبول، ۰ خطا** (`browser-results.json`)

| # الزام | نتیجهٔ واقعی |
|---|---|
| ۱ فهرست با نشست معتبر | ۴ نهاد seed با «نسخهٔ ۵» سرور؛ نام‌های نمونهٔ `data.js` دیده نمی‌شوند؛ هر ردیف دکمهٔ حذف + «صفحهٔ عمومی»؛ بدون کنترل انتشار/پنهان محلی |
| ۲ افزودن | راه تماس `javascript:` قبل از هر درخواست رد شد؛ با `mail` معتبر → PATCH فقط `{partners}`+`expected_version`؛ `/api/public/site-content` نهاد جدید را با همهٔ فیلدها دارد؛ `/partner.html?id=org…` → 200، `index,follow`، canonical، عنوان؛ خانه آن را در `#logoWall` نشان می‌دهد |
| ۳ ویرایش + reload | تغییر نام و لوگو پس از `reload` در فهرست، API عمومی و صفحهٔ اختصاصی (title، `og:image`، canonical) باقی است |
| ۴ حذف + reload | confirm صریح؛ پس از reload: غایب از فهرست، API عمومی، خانه؛ صفحهٔ اختصاصی 404؛ `qa-ev-1.partnerId` و سایر دسته‌ها بایت‌به‌بایت دست‌نخورده |
| ۵ مرز عمومی | نمای مالک و API عمومی فقط ۴ نهاد منتشرشده را می‌دهند؛ رکوردهای `unpublished/private/paused/pending` هرگز به پنل نمی‌رسند |
| ۶ بدون نشست | `admin.html#partners` فقط دروازهٔ ورود؛ `GET/PATCH` مالک → 401؛ محتوا تغییر نکرد |
| ۷ هم‌زمانی / نسخهٔ کهنه | نشست دوم نهاد دیگری را تغییر داد (v9→v10)؛ ذخیرهٔ UI با نسخهٔ کهنه → 409؛ تغییر شخص دیگر حفظ، تغییر من اعمال نشد، پیش‌نویس باز ماند؛ ذخیرهٔ دوباره هر دو تغییر را نگه داشت |
| ۸ دسته‌های دیگر | snapshot `events/people/articles/banners/library/cooperation` قبل و بعد از همهٔ عملیات یکسان |
| ۹ دادهٔ مخرب | لوگوی `//evil…` و وبگاه با اعتبارنامه در کلاینت رد؛ نام `<img onerror>` و شرح `<script>` به‌صورت متن ذخیره، در پنل و صفحهٔ عمومی escape، بدون alert/خطای JS |
| ۱۰ SEO پس از ویرایش | عنوان، canonical و `og:image` با دادهٔ ویرایش‌شده |
| ۱۱ موبایل ۳۹۰×۸۴۴ تاریک + دسکتاپ ۱۲۸۰×۸۰۰ روشن/تاریک | فهرست و ویرایشگر بدون اسکرول افقی، بدون خطای JS (اسکرین‌شات‌ها) |
| ۱۲ خطای شبکه | PATCH قطع‌شده → «به API همین سرور دسترسی نیست؛ هیچ تغییری ذخیره نشد»؛ ویرایشگر باز؛ API عمومی بدون تغییر |

پایان آزمون: پایگاه تست دوباره ۴ نهاد seed دارد.

### ۴-ب. mock (jsdom + API ساختگی با نسخه‌بندی) — `admin-partners-server.test.mjs` → **۲۳ قبول، ۰ خطا**
پوشش: بارگذاری از سرور، افزودن/ویرایش/ترتیب با `expected_version` صحیح، 409 با حفظ تغییر دیگری و پیش‌نویس، حذف با confirm و دست‌نخوردن رویداد، 401/500/قطع شبکه بدون موفقیت کاذب، نقش مدیر (نه مالک) به مدیریت نمی‌رسد و PATCH نمی‌فرستد، 401 هنگام بارگذاری + تازه‌سازی. این نتایج mock هستند و جایگزین ۴-الف نیستند.

### ۴-ج. رگرسیون
| مجموعه | نتیجه |
|---|---|
| `admin.test.mjs` (حالت fixture) | ۸۱۷ بررسی، ۰ خطا (رفتار محلی قبلی حفظ شد) |
| `admin-rbac.test.mjs` | قبول |
| `asset-audit.test.mjs` | 3/0 |
| `node tools/run-unit-tests.cjs` (همهٔ مجموعه‌ها) | **Nora suites: 25/25 passed; 0 failed** (شامل مجموعهٔ جدید؛ smoke ۷۹۱، admin ۸۱۷، support ۱۷۹، events-page ۶۸، …) — `unit-tests-summary.log` |
| `pytest -q tests` بک‌اند (بدون تغییر بک‌اند در این مرحله) | **220 passed, 4 skipped** (skipهای پیشینی Postgres) — `pytest-summary.log` |

## ۵. اسکرین‌شات‌ها (`Final-Delivery/reports/evidence-partner-management-2026-10-18/`)
`admin-partners-desktop-light.png`, `admin-partners-desktop-dark.png`, `admin-partners-mobile-dark.png`, `admin-partner-editor-desktop-light.png`, `admin-partner-editor-mobile-dark.png`, `admin-partner-conflict-desktop.png` (پیام ۴۰۹ با پیش‌نویس باز)، `partner-managed-after-edit-desktop.png` (صفحهٔ عمومی نهادِ ساخته‌شده از پنل).

## ۶. خطاها/محدودیت‌های باقی‌مانده (صادقانه)
1. **بدون پیش‌نویس/توقف سرورسمت:** نمای مالک برای نهادها همان نمای عمومی است؛ پنل فقط فهرست منتشرشده را مدیریت می‌کند (طبق خواستهٔ این مرحله). پیامد: اگر رکورد غیرعمومی‌ای مستقیماً با API خام ذخیره شده باشد، در پنل دیده نمی‌شود و ذخیرهٔ بعدی پنل (جایگزینی دستهٔ `partners`، قرارداد موجود API) آن را از رکورد حذف می‌کند. در UI هیچ راهی برای ساخت چنین رکوردی نیست. اگر پیش‌نویس سرورسمت لازم شد، نیازمند تصمیم (نمای مالک جدا + وضعیت در مدل) است.
2. ترتیب نهادها = ترتیب آرایهٔ سرور؛ هر جابه‌جایی یک PATCH است.
3. ویزارد رویداد در تولید همچنان رویداد را روی سرور منتشر نمی‌کند (محدودیت پیشینی، خارج از این مرحله)؛ فقط فهرست انتخاب نهاد از سرور می‌آید.
4. آزمون روی سرور تست محلی انجام شد، نه دامنهٔ زنده.
5. ورود در آزمون مرورگر از طریق فرم واقعی `login.html?mode=staff` و `/api/auth/staff-login` بود؛ تزریق تعارض با همان کلاینت `owner-api.js` در نشست مالک انجام شد.

## ۷. محدودهٔ کار
بدون endpoint/جدول/migration جدید؛ بدون تغییر بک‌اند در این مرحله؛ بدون تغییر در `partner.html`, SEO، مرز انتشار و صفحات دیگر؛ منطق ورود/مالکیت دست‌نخورده (مجوز در سرور: `require_owner`/`require_owner_write`).

## ۸. فایل‌های تغییرکرده
- کامیت `3faae21`: `Final-Delivery/website/nora-ui/admin.js`, `admin.html`, `site-content-sync.js`, `admin.test.mjs` (پین‌ها).
- کامیت تست/گزارش: `admin-partners-server.test.mjs` (جدید)، این گزارش، `evidence-partner-management-2026-10-18/` (اسکرین‌شات‌ها، `browser-results.json`, `unit-tests-summary.log`, `pytest-summary.log`, `tools/`).

## ۹. وضعیت گیت
- `3faae21` — قابلیت (admin.js/admin.html/site-content-sync.js + پین).
- کامیت بعدی — تست mock جدید، گزارش و شواهد. هر دو روی `arena/840de336-strix` push می‌شوند (بدون force)؛ هش نهایی در پاسخ پایانی و `git log origin/arena/840de336-strix`.
- PR #1 باز و ادغام‌نشده می‌ماند؛ هیچ deploy/release انجام نشده است.
