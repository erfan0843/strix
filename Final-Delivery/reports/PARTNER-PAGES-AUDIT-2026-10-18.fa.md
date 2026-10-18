# گزارش تکمیل صفحهٔ اختصاصی نهادهای همکار نورا و ممیزی کیفیت — ۱۴۰۵/۰۷/۲۶ (2026-10-18)

- مخزن: `erfan0843/strix` — شاخه: `arena/840de336-strix` — PR #1 همچنان **باز** است (ادغام/انتشار/استقرار انجام **نشده** و در این مرحله مجاز نبوده است).
- نقطهٔ شروع واقعی: `fef8883` (آخرین کامیت شاخه در origin؛ با `git fetch` + `git reset --hard origin/arena/840de336-strix` تأیید شد).
- کامیت‌های این مرحله (به‌ترتیب): `50bee69` (بک‌اند: مرز انتشار + فیلدها + SEO + تست‌ها)، `166fe93` (رابط: صفحهٔ `partner.html` + لینک‌های واقعی)، و کامیت سوم «تست‌ها + گزارش + شواهد» که هش نهایی آن در انتهای همین گزارش (بخش ۱۲) ثبت شده است.
- محیط آزمون: سرور تست ایزوله روی SQLite موقت (`/tmp/nora-preview`)، فقط دادهٔ آزمایشی با برچسب «(دادهٔ تست)». هیچ دادهٔ واقعی خوانده/نوشته نشده است. هیچ رازی (توکن/رمز) در شواهد وجود ندارد (`owner_api.py` رمز را از فایل محلیِ خارج از مخزن می‌خواند).

---

## ۱. معماری «قبل» (ردیابی روی کد واقعی)

| لایه | وضعیت قبل |
|---|---|
| پنل مالک (`admin.js` L3784–3850، `ppPartnerClean`) | فرم نهاد همکار فیلدهای `id,n,type,s,collab,since,focus,d,logo,href,links,mon,g,pub` را می‌سازد. |
| مسیر انتشار | `site-content-sync.js` فهرست‌های محلی (رویداد/افراد/مطالب/نهادها/کتابخانه) را **فقط در حالت fixture** به سرور می‌فرستد (`if(!TEST_FIXTURE_MODE) return []`). در تولید، نهادها فقط از طریق `PATCH /api/owner/site-content` (API مالک) به سرور می‌رسند — همان مسیری که در این ممیزی برای seed استفاده شد. |
| پاک‌ساز سرور (`backend/site_content.py::_partner`) | فقط `id,n,type,d,logo,href,g,mon` را نگه می‌داشت؛ `s,collab,since,focus,links` پنل **حذف** می‌شد. مرز انتشار فقط `hidden` و `status=draft` را رد می‌کرد. |
| رابطهٔ رویداد↔نهاد | ویزارد مالک `partnerId` را روی رویداد ذخیره می‌کند؛ ولی `_event` سرور آن را **حذف** می‌کرد → در تولید هرگز نهادِ رویداد نمایش داده نمی‌شد. |
| خانه (`home.html`) | کارت‌های `#logoWall` به‌صورت `<button data-partner>` بودند و یک شیت درون‌صفحه‌ای (`#shPartner`) باز می‌کردند؛ نشان‌های پاورقی `<span>` تزئینی؛ لینک‌های `home.html#partner=<id>` در `ui.js`/`event-page.js`. صفحهٔ مستقل، URL پایدار، متادیتای سرور و ورود به نقشهٔ سایت وجود نداشت. |
| SEO (`seo.py`/`app.py`) | انواع پویا: `event`, `person`, `post`؛ نوع `partner` وجود نداشت. |

شواهد «قبل»: `evidence-partner-audit-2026-10-18/before/` (کارت‌های دکمه‌ای + شیت؛ در شیت، لینک‌های تماس به‌صورت خام `mailto:`/`tel:` نمایش داده می‌شد).

---

## ۲. نتیجهٔ آزمون مرز انتشار (بازتولید شد — نقص واقعی بود)

قبل از اصلاح، با فراخوانی مستقیم `public_site_content(sanitize_site_content(...))` روی هفت رکورد غیرعمومی:

| رکورد | قبل | بعد |
|---|---|---|
| `pub: False` | **نشت می‌کرد** | رد می‌شود |
| `privacy: private` | **نشت می‌کرد** | رد می‌شود |
| `pend: True` | **نشت می‌کرد** | رد می‌شود |
| `status: paused` | **نشت می‌کرد** | رد می‌شود (در `site_content.py` و `seo.py`) |
| `status: pending` | **نشت می‌کرد** | رد می‌شود |
| `status: draft` | رد می‌شد | رد می‌شود |
| `hidden: True` | رد می‌شد | رد می‌شود |

اصلاح در **مرز اعتماد سرور** انجام شد: `_partner` اکنون از همان `_public_record` مشترک با افراد/رویدادها عبور می‌کند. آزمون پایدار در `backend/tests/test_site_content_api.py` (بخش نهادها) و `test_seo_routes.py` اضافه شد. در سرور تست نیز با seed هشت نهاد (۴ عمومی + ۴ غیرعمومی)، `/api/public/site-content` دقیقاً چهار شناسهٔ عمومی را برمی‌گرداند و `partner.html?id=qa-partner-{unpublished,private,paused,pending}` همگی **HTTP 404 + noindex** هستند و نام آن‌ها در HTML نیست.

### تزریق/URL
- نام/نوع/شرح با HTML (`<img onerror>`, `<script>`): در SSR به‌صورت escape (`&lt;img …&gt;`) و در صفحه به‌صورت متن بی‌اثر نمایش داده شد؛ هیچ dialog/تصویر/اسکریپت/لینکی ساخته نشد (آزمون مرورگر «xss»).
- `logo: javascript:…` → حذف؛ `href: https://user:pw@…` (اعتبارنامه در URL) → حذف؛ لینک‌های `javascript:` و `//host` (protocol-relative) و نوع ناشناختهٔ `other` → حذف در سرور (`_contact_links`) و بار دیگر در کلاینت (`websiteHref`/`contactHref`/`safeImage`).

---

## ۳. تغییرات بک‌اند (کامیت `50bee69`)

| فایل | تغییر |
|---|---|
| `backend/site_content.py` | `_contact_links()` مشترک (allowlist `tel,mail,tg,ig,web`؛ `_person` هم از آن استفاده می‌کند)؛ `_partner` با `_public_record` + فیلدهای اعتبارسنجی‌شدهٔ `s≤600`, `collab≤160`, `since≤80`, `focus` (حداکثر ۱۲×۶۰)، `links`؛ `href` بدون پروتکل → `https://`؛ `"paused"` رد می‌شود؛ `_event` فیلد `partnerId` را نگه می‌دارد (`partnerName` نگه داشته نمی‌شود تا نام کهنه منتشر نشود). قرارداد قبلی (`id,n,type,d,logo,href,g,mon`) دست‌نخورده است؛ بدون مهاجرت/جدول/endpoint جدید. |
| `backend/seo.py` | نوع `partner`: `canonical_path` → `/partner.html?id=<encoded>`؛ `sitemap_xml` فقط نهادهای منتشرشده از همان نمای عمومی؛ `structured_data(profile_entity=)` → `ProfilePage` + `mainEntity: Organization` (فقط `name/description/url/logo/image` واقعی؛ بدون آدرس/تلفن/امتیاز/تعداد کارمند)؛ `dynamic_page_values` عنوان «{نام} | نهادهای همکار نورا»، توضیح `s` → `d` → «{نام}، نهاد همکار گروه فرهنگی خط زندگی در نورا.». |
| `backend/app.py` | `_seo_html_response`: پشتیبانی `partner` در fallback آیتم/ناموجود، نقشهٔ کلید/تصویر OG، عنوان ۴۰۴ «نهاد همکار پیدا نشد | نورا»، بدنهٔ «این نهاد همکار در دسترس نیست». |
| تست‌ها | `test_site_content_api.py` (+۸۲ خط)، `test_seo_routes.py` (+۵۸ خط). |

canonical هرگز از `Host` ساخته نمی‌شود (همان `NORA_PUBLIC_BASE_URL` قبلی؛ در محیط تست که این متغیر خالی است canonical نسبی و sitemap طبق رفتار موجود 503 می‌دهد — پوشش sitemap در pytest با base URL انجام شده).

---

## ۴. تغییرات رابط (کامیت `166fe93`)

| فایل | تغییر |
|---|---|
| `partner.html` (جدید) | همان اسکلت `person.html`: topbar، breadcrumb، `main#partnerMain`، `.tabbar` (خانه/رویدادها/نهادهای همکار)، `lang=fa dir=rtl`، `public-data.js?v=111` + `ui.js?v=127`؛ `data.js` فقط در حالت fixture (`document.write` شرطی، مثل سایر صفحات). |
| `partner-page.js` (جدید، `?v=1`) | داده فقط از `NORA_PUBLIC.partners` (snapshot سرور). رندر: لوگو (با fallback نشان حرفی روی گرادیان مجاز) یا نشان حرفی؛ `h1` نام؛ نوع؛ `s` (لید)؛ تگ‌های `focus`؛ دکمهٔ «وبگاه رسمی» با نمایش میزبان، `target=_blank rel="noopener noreferrer"`؛ کارت‌های «نوع همکاری/همکاری از» فقط اگر مقدار داشته باشند؛ «معرفی» (`d` با حفظ خط جدید)؛ «راه‌های ارتباط رسمی» (`mail/tel/tg/ig/web`)؛ «رویدادهای پیش‌رو/برگزارشده با این نهاد» فقط از `event.partnerId === partner.id`؛ حالت ناموجود («این نهاد همکار در دسترس نیست») و حالت قطع API («محتوای زنده در دسترس نیست») جدا؛ بدون آمار صفر/متن ساختگی/کارت خالی. |
| `partner-page.css` (جدید، `?v=1`) | روی توکن‌های `nora.css`؛ لوگوی مربع ۹۲/۱۱۰px با `object-fit: contain`؛ عرض خواندن؛ `overflow-wrap:anywhere` برای نام/URL طولانی؛ حالت تاریک؛ focus-visible. |
| `home.html` | کارت‌های `#logoWall` → `<a class="logo" href="partner.html?id=…">` (با `aria-label`)؛ نشان‌های پاورقی → لینک (`.hfoot .flogo`)؛ شیت `#shPartner` و `openPartner` حذف؛ hash قدیمی `#partner=<id>` → `location.replace('partner.html?id=…')`؛ لوگوی شکسته در خانه → نشان حرفی. |
| `ui.js` (`v127`) | دو لینک نهاد (`.mi-partner`, کارت رویداد) → `partner.html?id=`؛ آیکن تب «نهادهای همکار» (`TAB_ICON_PATHS.partners`). حجم: 218,913 بایت (< سقف asset-audit). |
| `event-page.js` (`v102`) | لینک نهادِ رویداد → `partner.html?id=`. |
| `public-data.js` (`v111`) | `normalizePartner` فیلدهای جدید را عبور می‌دهد. |
| پین‌ها | `public-data.js?v=111` (۶ صفحه + `support.test.mjs`)، `ui.js?v=127` (۱۲ صفحه)، `event-page.js?v=102`. |

### فیلدهای نمایش‌داده‌شده و منبع آن‌ها
| فیلد | پنل مالک | سرور (بعد) | صفحه |
|---|---|---|---|
| `id,n,type,d,logo,href,g,mon` | ✓ | ✓ (قبلاً هم) | ✓ |
| `s,collab,since,focus` | ✓ | ✓ (**جدید؛ قبلاً حذف می‌شد**) | ✓ فقط اگر مقدار داشته باشد |
| `links` | ✓ | ✓ با allowlist (**جدید**) | ✓ |
| رویدادهای مرتبط | `event.partnerId` از ویزارد | ✓ (**جدید؛ قبلاً حذف می‌شد**) | ✓ فقط رابطهٔ صریح |
| مطالب مرتبط | رابطه‌ای در مدل داده وجود ندارد | — | نمایش داده نمی‌شود (محدودیت ثبت‌شده) |

تفاوت fixture با سرور: در حالت fixture، `data.js PARTNERS` و `site-content-sync` همان شکل داده را تولید می‌کنند؛ صفحهٔ جدید در تولید به هیچ‌کدام وابسته نیست.

---

## ۵. SEO / canonical / داده‌های ساخت‌یافته / نقشهٔ سایت (خروجی واقعی سرور تست)

```
GET /partner.html?id=qa-partner-1                      → 200
  <title>نهاد همکار آزمایشی (دادهٔ تست) | نهادهای همکار نورا</title>
  <meta name="robots" content="index,follow"/>  <meta property="og:type" content="website"/>
  <meta property="og:image" content="/icon-192.png"/>  <link rel="canonical" href="/partner.html?id=qa-partner-1"/>
  JSON-LD: Organization(سایت) + WebSite + ProfilePage{mainEntity: Organization{name, description, url:https://example.org/partner-test}}
  یک <h1>؛ <html lang="fa" dir="rtl">
GET /partner.html?id=qa%20partner%2F2%20%C3%BC          → 200، canonical با همان شناسهٔ encode‌شده
GET /partner.html?id=qa-partner-private                 → 404، «نهاد همکار پیدا نشد | نورا»، noindex,nofollow,noarchive، بدون canonical
GET /partner.html?id=nope و /partner.html (بدون id)     → 404 به همان شکل
```
pytest (`test_seo_routes.py`): canonical مطلق با base URL، `og:image` لوگو، breadcrumb «خانه → نهادهای همکار (/#partners) → نام»، `partner-plain` با توضیح fallback، هفت حالت غیرعمومی → 404، و sitemap فقط شامل نهادهای منتشرشده.

---

## ۶. آزمون‌های مرورگر واقعی (Playwright + Chromium، سرور تست، ۳۹۰×۸۴۴ و ۱۲۸۰×۸۰۰، روشن + تاریک)

اسکریپت: `evidence-partner-audit-2026-10-18/tools/partner-verify.mjs` — نتیجهٔ واقعی: **۷۴ قبول، ۰ خطا** (`after/browser-results.json`).

| # سناریوی درخواست | نتیجه |
|---|---|
| ۱ صفحهٔ نهاد با همهٔ فیلدها (۴ ترکیب اندازه/تم) | ✓ 200، منبع `server`، یک `h1`، نوع/لید/کارت‌ها/تگ‌ها/شرح، لوگو بارگذاری‌شده |
| ۲ کلیک از خانه → همان شناسه | ✓ موبایل و دسکتاپ؛ `Back` مرورگر به خانه با بخش نهادها |
| ۳ URL مستقیم + reload | ✓ |
| ۴ بدون لوگو | ✓ نشان حرفی «طو» |
| ۵ نام/شرح/URL طولانی و شناسهٔ دارای فاصله/اسلش/یونیکد | ✓ بدون اسکرول افقی؛ شناسه encode‌شده |
| ۶ غیرعمومی از طریق صفحه و API | ✓ چهار شناسهٔ غیرعمومی 404 و غایب از API |
| ۷ شناسهٔ ناموجود | ✓ HTTP 404 واقعی + noindex + پیام انسانی + لینک بازگشت |
| ۸ HTML/URL مخرب | ✓ متن بی‌اثر؛ بدون dialog/img/script/لینک؛ SSR escape‌شده |
| ۹ وبگاه/تماس‌ها | ✓ `https://example.org/partner-test` با `noopener noreferrer`؛ `mailto`/`tel`/`t.me` درست؛ `javascript:`/`other` حذف |
| ۱۰ canonical/OG/JSON-LD | ✓ (curl بالا + pytest) |
| ۱۱ sitemap | ✓ در pytest؛ در محیط تست بدون base URL طبق رفتار قبلی 503 (ثبت شد) |
| ۱۲ روابط فقط واقعی | ✓ دو رویداد با `partnerId=qa-partner-1` (یک پیش‌رو، یک برگزارشده)؛ نهاد بدون رویداد → بخش نمایش داده نمی‌شود |
| ۱۳ بدون داده / قطع API / لوگوی شکسته | ✓ پیام‌های جدا؛ لوگوی 404 → نشان حرفی؛ بدون خطای JS (تنها لاگ شبکهٔ 404 منبعِ عمداً شکسته) |
| ۱۴ کیبورد/فوکوس | ✓ Tab به دکمهٔ وبگاه می‌رسد، حلقهٔ فوکوس مرئی (`after/partner-desktop-focus.png`) |
| ۱۵ سلامت سایر صفحات | ✓ خانه و رویداد در همین اسکریپت؛ بقیه در ۲۴ مجموعهٔ واحد (زیر) |
| ۱۶ سازگاری asset-audit/SEO/public-content | ✓ |

اسکرین‌شات‌ها: `after/home-partners-{mobile,desktop}.png`، `after/partner-{mobile,desktop}-{light,dark}[-full].png`، `after/partner-long-mobile.png`، `after/partner-broken-logo-desktop.png`، `after/partner-xss-desktop.png`، `after/partner-missing-mobile.png`، `after/partner-unavailable-mobile.png`؛ «قبل»: `before/home-partners-*.png`، `before/home-partner-detail-*.png`.

در حین آزمون سه مورد دیده و همان‌جا اصلاح شد: آیکن‌های متنی رویداد که در فونت سیستم رندر نمی‌شدند (→ SVG درون‌خطی)، کنتراست کم میزبان روی دکمهٔ وبگاه، آیکن تکراری تب.

---

## ۷. آزمون‌های خودکار (خروجی واقعی)

| مجموعه | نتیجه |
|---|---|
| `node tools/run-unit-tests.cjs` | **Nora suites: 24/24 passed; 0 failed** — از جمله `smoke` ۷۹۱ قبول/۰ خطا (شامل ادعاهای جدید صفحهٔ نهاد، XSS، ناموجود، آفلاین)، `admin` ۸۱۷، `support` ۱۷۹، `events-page` ۶۸، `asset-audit` 3/0، `audit-regression`، `post`, `account*`, `login`, `service-worker-privacy`, `site-content-sync`, … (`unit-tests-summary.log`) |
| `pytest -q tests` (بک‌اند) | **220 passed, 4 skipped** (۴ skip پیشینی: Postgres آزمایشی پیکربندی‌نشده) (`pytest-summary.log`) |
| `mypy backend` | Success: no issues found in 48 source files |

تغییرات تست: `smoke.test.mjs` (بلوک شیت قدیمی → ادعاهای لینک/صفحهٔ نهاد؛ فهرست متادیتا شامل `partner.html?id=o1`)، `asset-audit.test.mjs` و `tools/browser-audit.cjs` (افزودن `partner.html`)، `events-page.test.mjs`/`support.test.mjs` (پین‌ها).

---

## ۸. محدودیت‌ها (صادقانه)

1. **مسیر انتشار در تولید (پیشینی):** پنل مدیریت فهرست نهادها را فقط در حالت fixture با سرور همگام می‌کند؛ در تولید تنها مسیر، API مالک (`PATCH /api/owner/site-content`) است. ساخت UI سرورسمتِ مدیریت نهادها خارج از این ممیزی و نیازمند تصمیم انسانی است.
2. **مطالب ↔ نهاد:** مدل داده رابطه‌ای ندارد؛ هیچ رابطهٔ حدسی ساخته نشد.
3. **sitemap در محیط تست** به‌دلیل نبود `NORA_PUBLIC_BASE_URL` (رفتار موجود) 503 است؛ در pytest با base URL تأیید شد، نه روی سرویس زنده.
4. آزمون‌ها روی سرور تست محلی هستند؛ تأیید روی دامنهٔ زنده انجام نشده است.
5. در SSR fallback، `h1` قبل از هیدراسیون همان عنوان کامل است (الگوی موجود `person.html`؛ تغییر داده نشد).

## ۹. موارد نیازمند بازبینی انسانی
- تصمیم دربارهٔ مدیریت سرورسمت نهادها در پنل (بند ۸-۱).
- آیا نشان‌های پاورقی باید به صفحهٔ نهاد لینک شوند (اجرا شده) یا تزئینی بمانند.
- اگر لوگوهای واقعی بیرون از origin میزبانی می‌شوند، سیاست `og:image` مطلق با `NORA_PUBLIC_BASE_URL` بررسی شود.

## ۱۰. پذیرش
- هر نهاد منتشرشده از خانه (کارت، پاورقی، چیپ رویداد) به صفحهٔ اختصاصی با URL پایدار می‌رسد ✓
- URL مستقیم + reload ✓ — متادیتا و sitemap درست ✓ — خصوصی/ناموجود هرگز از مرز عمومی عبور نمی‌کند (با تست) ✓ — بدون رگرسیون (24/24، 220 pytest) ✓

## ۱۱. فایل‌های تغییریافته
بک‌اند: `backend/site_content.py`, `backend/seo.py`, `backend/app.py`, `backend/tests/test_site_content_api.py`, `backend/tests/test_seo_routes.py`.
رابط: جدید `partner.html`, `partner-page.js`, `partner-page.css`؛ ویرایش `home.html`, `ui.js`, `event-page.js`, `public-data.js` و پین‌ها در `account/admin/builder/create/event/events/form/login/person/post/support.html`.
تست/ابزار: `smoke.test.mjs`, `asset-audit.test.mjs`, `events-page.test.mjs`, `support.test.mjs`, `tools/browser-audit.cjs`.
گزارش/شواهد: این فایل + `evidence-partner-audit-2026-10-18/`.

## ۱۲. وضعیت گیت
در انتهای کار، سه کامیت روی `arena/840de336-strix` push شد (بدون force): `50bee69`، `166fe93` و کامیت تست/گزارش. هش نهایی و وضعیت push در پاسخ پایانی و در `git log origin/arena/840de336-strix` قابل تأیید است. PR #1 باز مانده؛ هیچ ادغام/انتشار/استقراری انجام نشده است.
