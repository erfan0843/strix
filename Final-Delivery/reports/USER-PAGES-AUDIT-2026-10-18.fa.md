# ممیزی جامع صفحات کاربر نورا و بهبود تدریجی — ۱۴۰۵/۰۷/۲۶ (2026-10-18)

- مخزن: `erfan0843/strix` — شاخه: `arena/840de336-strix` — PR #1 همچنان **باز** است (ادغام/انتشار/استقرار انجام **نشده**).
- نقطهٔ شروع واقعی: `59f971f` (با `git status` تمیز و `git log` برابر با origin تأیید شد).
- کامیت‌های این مرحله (به‌ترتیب، همه روی همین شاخه push شده‌اند): `e977786` (بک‌اند: مرز خواندن محتوای غیرعمومی)، `4da368b` (رابط کاربر: اصلاح‌های P1)، `31e6b52` (رابط کاربر: بهبودهای P2)، `b8d1542` (دسترس‌پذیری: h1 فرم نایافته + `<main>` آفلاین) و کامیت پایانی «گزارش + شواهد» `de18a23` (این خط در کامیت تکمیلی ثبت شد).
- اصل حاکم: **بهبود بدون تغییر بنیادین** — هیچ صفحه‌ای بازنویسی نشد، ساختار صفحه‌ها، هویت بصری نورا، RTL فارسی، قرارداد APIها، مدل داده و احراز هویت دست‌نخورده ماند. هیچ endpoint، جدول، migration یا وابستگی تازه‌ای اضافه نشد.
- محیط آزمون: سرور تست ایزوله (`uvicorn` روی SQLite موقت در `/tmp/nora-preview`، مالک آزمایشی `preview-owner`) با دادهٔ برچسب‌دار «(دادهٔ تست)». **هیچ دامنهٔ زنده‌ای آزموده نشده** و هیچ دادهٔ واقعی خوانده/نوشته نشده است. در شواهد هیچ راز/کوکی/توکن/pepper وجود ندارد (اسکن شد؛ بخش ۱۰).

---

## ۱. نقشهٔ صفحات و مسیرهای واقعی

منبع: grep روی `href=`/`location`/`?id=`/`?fid=` در همهٔ HTML/JS، مسیرهای `backend/app.py` (`/`, `/{page}.html` → `_seo_html_response`، `/form.html?fid=` رندر سروری، ناشناخته → `404.html` با HTTP 404)، و خزش واقعی لینک‌ها روی سرور تست (`evidence/pages-audit-before.json` → کلید `__links`؛ ۵۲ مقصد داخلی، همه 200 جز یک لینک fixture پنهان، بخش ۹).

| دسته | صفحه | ورودی‌ها (از کجا می‌آید) | خروجی‌ها (به کجا می‌رود) | دادهٔ لازم / منبع واقعی | وابستگی نشست |
|---|---|---|---|---|---|
| عمومی | `index.html` | ریشهٔ سایت `/` | `home.html` (meta refresh + لینک) | — | ندارد |
| عمومی | `home.html` | index، نوار پایین همهٔ صفحه‌ها، 404، آفلاین | `events(#cat/#list/?ev=/?status=past)`, `event?id=`, `post?id=`, `person?id=`, `partner?id=`, `form?fr=`, `account#book`, `login?mode=server&next=account.html`, `support` | `GET /api/public/site-content` (رویداد/مطلب/افراد/نهاد/بنر) | ندارد؛ وضعیت ورود فقط برای برچسب حساب |
| عمومی | `events.html` (+`?status=past`, `#list/#cat/#lib`) | خانه، نوار پایین، event، post | `event?id=`, `home#teachers`, `account`, `support` | `site-content` (رویدادها) | ندارد |
| عمومی | `event.html?id=` | events، خانه، post، account | `form?fid=` (CTA ثبت‌نام)، `events`, `home#teachers`, `person`, `partner` | `site-content` + متادیتای سروری `seo.py` | ندارد |
| عمومی | `post.html?id=` | خانه (`#articles`)، post (پیشنهادها) | `event?id=`, `events#lib`, `home#articles`, `post?id=`, `support` | `site-content` (articles) | ندارد |
| عمومی | `person.html?id=` / `partner.html?id=` | خانه، event | `events#list`, `home#teachers/#partners` | `site-content` (people/partners) | ندارد |
| ورود/استفاده | `login.html` (`?mode=server|staff&next=`) | خانه، account (مهمان)، نوار پایین | `account`, `admin.html#dash` (staff), `support(#reader)`, `home`, `events` | `POST /api/auth/phone-otp/request|verify` (عضو)، `POST /api/auth/login` (کارکنان)، `GET /api/auth/me` | می‌سازد |
| ورود/استفاده | `account.html` (`#events/#forms/#profile/#payments/#book`) | خانه، نوار پایین، login (next) | `login?mode=server&next=account.html`, `events`, `home`, `support` | `GET /api/account/me` (+ ثبت‌نام‌ها/فایل‌ها) | لازم؛ مهمان → نمای معرفی |
| ورود/استفاده | `form.html?fid=` (+`&kind=reg`, `?fr=`) | event (CTA)، خانه، لینک مستقیم | `final-page-review.html?fid=` پس از ثبت، `home` (+ `events` در حالت u12) | رندر سروری فرم منتشرشده، `POST /api/public/forms/{id}/responses`، پرداخت (در این محیط غیرفعال) | ندارد (ثبت‌نام مهمان) |
| ورود/استفاده | `final-page-review.html?fid=` | form (پس از تکمیل) | `home.html` (**جدید**) | بلیت/پیگیری سروری | ندارد |
| کمک/ویژه | `support.html` (`#reader`) | خانه، نوار پایین، login، event، post | `account`, `events`, `home(#notice)` | `site-content` (تماس‌های منتشرشده) | ندارد |
| کمک/ویژه | `404.html` / هر مسیر ناشناخته / شناسهٔ نامعتبر | سرور | `home`, `events`, `login`, `support` | — | ندارد |
| کمک/ویژه | `offline.html` | Service Worker (`sw.js` shell) | `home` + دکمهٔ تلاش مجدد | — | ندارد |
| ساخت فرم | `create.html`, `builder.html` | فقط از پنل مدیریت (`admin.html#money/#newev`) و از همدیگر | `admin`, `builder/create`, `form?preview=1`, `final-page-review`, `index`, `login?mode=server` | `site-content` + APIهای مالک (پشت نشست کارکنان) | لازم (نقش کارکنان؛ مرز با پنل: این دو صفحه «ابزار» پنل‌اند و از هیچ صفحهٔ کاربر عمومی لینک نمی‌شوند) |
| پیش‌نمایش | `loading-preview.html`, `nora-pay-preview.html` | **هیچ لینکی از صفحه‌های تولیدی** (بررسی شد ✓) | — | — | — |

همهٔ صفحه‌ها `noindex` مناسب دارند جز صفحات عمومی (`index,follow` + canonical)؛ شناسهٔ نامعتبر در event/post/person/partner/form → **HTTP 404 + `noindex,nofollow,noarchive`** (جدول بخش ۲).

---

## ۲. وضعیت اولیهٔ همهٔ صفحه‌ها (خزش خودکار، سرور تست، ۵ ویوپورت)

ابزار: `evidence/tools/pages-audit.mjs` (Playwright/Chromium روی ۳۶۰×۸۰۰، ۳۹۰×۸۴۴، ۷۶۸×۱۰۲۴، ۱۲۸۰×۸۰۰، ۱۴۴۰×۹۰۰ + حالت تیره در ۳۹۰ + `prefers-reduced-motion`). خروجی کامل: `evidence/pages-audit-before.json`، لاگ: `evidence/logs/pages-audit-run1.log`، تصویرها: `evidence/shots/before/*.png`، شیت‌های مقایسه: `evidence/shots/sheets/`.

| صفحه | HTTP | robots | canonical / og:image | h1 | `main` / skip-link | هدف‌های لمسی <32px | ورودی بی‌برچسب | خطای JS / درخواست تکراری | سرریز افقی (۵ ویوپورت) | حجم بارگیری ۳۹۰ |
|---|---|---|---|---|---|---|---|---|---|---|
| home / index | 200 | index,follow | ✓ / icon-512 | 1 | ✓ / ✓ | ۶ (پین بنر ۳۰px، لوگوی پاورقی ۲۸px، لینک‌های متنی) | — | 0 / 0 | ندارد | 462 KB |
| events (+past) | 200 | index,follow | ✓ / icon-512 | 1 | ✓ / ✓ | ۶ (لینک‌های متنی درون کارت) | — | 0 / 0 | ندارد | 384 KB |
| event | 200 | index,follow | ✓ / icon-512 | 1 | ✓ / ✓ | ۴ | — | 0 / 0 | ندارد | 430 KB |
| event?id=نامعتبر | **404** | noindex,nofollow | — | 1 | ✓ / ✓ | 0 | — | 0 | ندارد | 330 KB |
| post | 200 | index,follow | ✓ / icon-512 | 1 | ✓ / ✓ | ۲ | — | 0 / 0 | ندارد | 375 KB |
| person | 200 | index,follow | ✓ / **ندارد** | 1 | ✓ / ✗ | ۲ | — | 0 / 0 | ندارد | 378 KB |
| partner | 200 | index,follow | ✓ / icon-**192** | 1 | ✓ / ✗ | ۲ | — | 0 / 0 | ندارد | 399 KB |
| login (+staff) | 200 | noindex,follow | **canonical روی صفحهٔ noindex** / og:image **روی میزبان خارجی** | 1 | ✓ / ✗ | 0 | — | 0 (۲ خط 401 مورد انتظار) | ندارد | 435 KB |
| account (مهمان) | 200 | noindex,follow | — / icon-512 | 1 | ✓ / ✗ | ۳ | — | 0 / 0 | ندارد | 515 KB |
| form?fid=منتشرشده | 200 | noindex,nofollow | — | 1 | ✗ / ✗ | 0 | — | 0 / 0 | ندارد | 419 KB |
| form?fid=نامعتبر / بدون fid | 404 / 200 | noindex | — | **0** | ✗ / ✗ | 0 | — | 0 | ندارد | 419 KB |
| final-page-review | 200 | noindex,follow | — | 1 | ✓ / ✗ | 0 | — | 0 | ندارد | 236 KB |
| support | 200 | noindex,follow | ✓ / icon-512 | 1 | ✓ / ✗ | ۳ | — | 0 / 0 | ندارد | 447 KB |
| 404 / مسیر ناشناخته | 404 | noindex,nofollow | — | 1 | ✓ / ✓ | ۱ (برند ۳۰px) | — | 0 | ندارد | **1,476 KB** (`404-art.png` = 1,274 KB) |
| offline | 200 | noindex,follow | — | 1 | **✗** / ✗ | 0 | — | 0 | ندارد | 193 KB |
| create | 200 | noindex,follow | — | 1 | ✓ / ✗ | 0 | **`#catSearch`** | 0 / 0 | ندارد | 417 KB |
| builder | 200 | noindex,follow | — | 1 | ✓ / ✗ | 0 | **`#rejNote`, `#msgText`, `#passNote`** | 0 | ندارد | 414 KB |
| loading-preview / nora-pay-preview | 200 | noindex,follow | — | 1 | ✓/✗ | 0 | — | 0 | ندارد | 342 / 419 KB |

یافته‌های عمومی خزش: هیچ تصویری بدون `alt` نیست؛ هیچ دکمه/لینکِ بی‌نام نیست؛ `lang=fa dir=rtl` همه‌جا؛ هیچ درخواست API تکراری؛ زمان بارگیری ۳۰–۱۶۰ms روی سرور محلی؛ حالت تیره در همهٔ صفحه‌های اصلی سازگار (`sheet-dark.png`)؛ `404`/`offline` حالت تیره ندارند (عمدی: صفحه‌های مستقل سبک). تنها درخواست‌های ناموفق: پروب‌های 401 مهمان در login و `/uploads/does-not-exist-qa.webp` که **دادهٔ تست** (نهاد با لوگوی شکسته) است، نه نقص.

---

## ۳. آزمون‌های جریانی واقعی (Playwright روی سرور تست، نه mock)

ابزار: `evidence/tools/flows-audit.mjs`. اجرای ۱ (قبل از اصلاح): **۴۲ قبول / ۵ رد** (`evidence/logs/flows-audit-run1.log`). اجرای ۲ (بعد از اصلاح، با ۶ سنجهٔ افزوده): **۵۳/۵۳ قبول** (`evidence/logs/flows-audit-run2.log`، تصویرها `evidence/shots/flows/`).

| # | جریان | چه چیزی واقعاً سنجیده شد | نتیجه |
|---|---|---|---|
| 1a–1k | رویدادها | جست‌وجو ۴→۱ رویداد؛ جست‌وجوی بی‌نتیجه → حالت خالی صادق؛ چیپ «برگزارشده» و deep-link `?status=past` فقط رویداد گذشته؛ تقویم ۳۰ خانه + پنل روز؛ کارت → صفحهٔ رویداد؛ CTA ثبت‌نام به `form?fid=` واقعی؛ راه بازگشت؛ بدون خطای JS | ✓ |
| 2a–2b | قطع API | با `route(abort)` روی `/api/public/site-content`: صفر کارت نمونه، پیام توضیحی «به پایگاه عمومی سرور دسترسی نیست» | ✓ |
| 3a–3h | ثبت‌نام فرم | گام الزامی خالی → ۲ نشانگر اعتبارسنجی درون‌خطی؛ `POST /responses` واقعی **200**؛ صفحهٔ تکمیل؛ بدون `alert()`؛ reload پس از ثبت از صفر شروع نمی‌کند؛ **صفحهٔ تکمیل راه بازگشت به خانه دارد (جدید)** و ناوبری بدون دیالوگ مسدودکننده | ✓ (3e2 قبلاً وجود نداشت) |
| 4a–4b | قطع شبکه هنگام ثبت | هرگز صفحهٔ موفقیت نشان نمی‌دهد؛ پیام تلاش مجدد | ✓ |
| 5a / 5a2 | ورود عضو — شمارهٔ نامعتبر | پیام درون‌خطی **قبل** از مصرف کپچا؛ **صفر** فراخوانی `/phone-otp/request` | ✓ (قبلاً رد: کپچا هدر می‌رفت، بخش ۴) |
| 5b–5c | ورود عضو — بدون سرویس پیامک | سرور 503 + پیام «سرویس ارسال کد روی سرور تنظیم نشده»؛ هیچ کد جعلی | ✓ |
| 5d–5f | ورود کارکنان | رمز غلط → 401 + پیام روشن، بدون redirect؛ `next=` خارجی هرگز open-redirect نمی‌شود | ✓ (رد اجرای ۱ فقط خطای regex اسکریپت بود، نه محصول) |
| 6a–6c | حساب مهمان | هدایت به `login?mode=server&next=account.html`؛ هیچ دادهٔ شخصی در نمای مهمان | ✓ |
| 7a–7b | پشتیبانی | بدون تماس منتشرشده، هیچ لینک خارجی/نمونه نشان نمی‌دهد | ✓ |
| 8 | کیبورد | ترتیب Tab + حلقهٔ فوکوس قابل‌دیدن روی `#q` خانه، `#eventSearch` رویدادها و فرم ورود | ✓ (قبلاً رد روی خانه/رویدادها) |
| 9a–9c | XSS | رویداد/مطلب/فرد با عنوان `<img onerror>`/`<script>`: صفر دیالوگ، صفر گرهٔ تزریقی، متن خام نمایش داده می‌شود | ✓ |
| 10a–10d | مطلب سروری | همرسانی/رونوشت فعال؛ رونوشت → کلیپ‌بورد `…/post.html?id=np-qa-1` + توست؛ بدون Web Share به رونوشت برمی‌گردد؛ canonical + og:title | ✓ (10a/10c/10d جدید) |
| 11a–11b | صفحه‌های انتهایی | `final-page-review` بدون context راه بازگشت دارد؛ آفلاین تلاش مجدد/خانه | ✓ (11a قبلاً «NO LINKS») |
| 12 | شناسه‌های نامعتبر | event/post/person/partner/form → 404 + noindex + لینک بازگشت | ✓ |

**آزموده نشد (نیازمند سرویس/اعتبار بیرونی؛ ادعا نمی‌شود):** ورود واقعی عضو با پیامک (Safir تنظیم نیست → 503 درست)، نمای حساب برای عضو واردشده روی سرور واقعی (فقط در تست‌های mock `account*.test.mjs` پوشش دارد)، مینی‌اپ بله، پرداخت کیف پول/کارت‌به‌کارت واقعی، آپلود فایل رسید، `sitemap.xml` (در محیط تست بدون `NORA_PUBLIC_BASE_URL` عمداً 503 fail-closed است).

---

## ۴. نقص‌ها و اصلاح‌ها (به‌ترتیب شدت)

| شدت | صفحه | نقص + بازتولید | اثر بر کاربر | اصلاح + فایل‌ها | آزمون و نتیجهٔ واقعی | شواهد |
|---|---|---|---|---|---|---|
| **P0 (مرز داده)** | `home/events/event/post/person` (API عمومی) | رکوردهای **غیرعمومی** (`private/hidden/paused/pending`) که مستقیم در `site_content` ذخیره شده باشند، در `events/people/articles` از `/api/public/site-content` **نشت می‌کردند**؛ فیلتر زمانِ خواندنِ افزوده‌شده در `9b248a3` فقط `partners` را می‌پوشاند. همچنین ذخیرهٔ پنل مالک (که فقط نمای عمومی را می‌بیند) می‌توانست این ردیف‌ها را حذف کند. بازتولید: تست پارامتری تازه در `backend/tests/test_partner_retention.py` → **۳ رد** در `59f971f`. | افشای محتوای منتشرنشده/خصوصی در صفحه‌های عمومی؛ از دست رفتن ردیف‌های غیرعمومی در ذخیرهٔ پنل | `backend/site_content.py`: `NON_PUBLIC_RETAINED_KEYS`, `retain_non_public_rows()` (نام قدیمی alias ماند)، حلقهٔ فیلتر در `public_site_content`; `backend/app.py`: PATCH مالک retention را روی هر چهار کلید اعمال می‌کند — **بدون تغییر قرارداد API/شِما** | قرمز: `logs/pytest-read-boundary-red.log` (3 failed) → سبز؛ کل pytest **225 passed, 4 skipped** (`logs/pytest-user-pages-2026-10-18.log`)؛ mypy تمیز | کامیت `e977786` |
| P1 | `login.html` | شمارهٔ آشکارا نامعتبر (مثلاً ۵ رقم) مستقیم به `/phone-otp/request` می‌رفت؛ سرور 422 می‌داد ولی **کپچا مصرف می‌شد** و کاربر باید کپچای تازه حل می‌کرد | اصطکاک ورود، پیام دیر | `login.js`: `normalizeIranPhone()` آینهٔ `backend/otp.py` فقط برای پیام زودهنگام + فوکوس روی فیلد؛ داور نهایی همچنان سرور (`login.js?v=127`) | 5a/5a2: پیام درون‌خطی، **۰** درخواست OTP؛ `login.test.mjs` سبز | `flows-audit-run2.log` |
| P1 | `final-page-review.html` | صفحهٔ تکمیل ثبت‌نام **هیچ لینکی** به سایت نداشت (بن‌بست؛ فقط دکمهٔ مرورگر) | کاربر پس از ثبت‌نام سرگردان | لینک «بازگشت به خانهٔ نورا» (۴۴px، حلقهٔ فوکوس)؛ `form.html` حالت u12 نیز `#serverEndNav` (خانه/رویدادها) می‌گیرد — مسیر عادی تکمیل همچنان به `final-page-review` می‌رود | 3e2/3h/11a | `shots/flows/form-done-390.png`, `shots/after/final-page-review-390.png` |
| P1 | `home.html`, `events.html` | فوکوس کیبورد روی فیلد جست‌وجو **قابل‌دیدن نبود** (outline داخل wrapper گم می‌شد) | کاربر کیبورد/کم‌بینا | `nora.css .sfield:focus-within` و `events-page.css .event-search:focus-within` حلقهٔ `brand-tint` (پین `nora.css?v=101`, `events-page.css?v=102`) | جریان 8 روی هر دو صفحه | `flows-audit-run2.log` |
| P1 | `login.html` | `og:image` به میزبان خارجی اشاره داشت و صفحهٔ **noindex** canonical داشت (سیگنال متناقض) | اشتراک‌گذاری/SEO نادرست | og:image → `icon-512.png` محلی؛ canonical حذف | خزش بعد: canonical خالی، og محلی (`pages-audit-after.json`) | `shots/after/login-390.png` |
| P1 (لمسی) | `home.html` | نقطه‌های پین بنر ۳۰×۳۰px | انگشت روی موبایل | `.pinb::after` ناحیهٔ ۴۴px بدون تغییر ظاهر | خزش بعد: گزارش «small» همان ظاهر ۳۰px را می‌بیند (hit-area نامرئی است)؛ کلیک دستی تأیید شد | کامیت `4da368b` |
| P2 | `post.html` | «همرسانی · غیرفعال» و «رونوشت نشانی · غیرفعال» حتی برای مطلب **منتشرشدهٔ سروری** | قابلیت واقعی اما خاموش | فقط وقتی `!localData&&!isPend&&!preview`: رونوشت نشانی عمومی با کلیپ‌بورد (+ fallback `execCommand`) و توست؛ همرسانی با `navigator.share` و fallback به رونوشت. پیش‌نمایش/محلی/در صف تأیید همان رفتار قبلی. بدون سرویس بیرونی | 10a/10c/10d روی سرور واقعی؛ `post.test.mjs` +۴ سنجه → **103 قبول** | `shots/after/post-390.png` |
| P2 (سرعت) | `404.html` / هر مسیر ناشناخته | صفحهٔ ۴۰۴ روی موبایل **1.48 MB** بود (`404-art.png` ۱٫۲۷ MB) | مصرف داده/کندی روی شبکهٔ ضعیف | `404-art.webp` (۲۵ KB، کیفیت ۸۲، بصری یکسان — `shots/sheets/404-png-vs-webp.png`) در `<picture>` با PNG به‌عنوان fallback (PNG حذف نشد؛ `server.test` آن را می‌خواهد) | خزش بعد: **198 KB** (`pages-audit-after.json`)؛ سرور `image/webp` 200؛ `asset-audit`/`server` تست سبز | `shots/before/404-390.png` ↔ `shots/after/404-390.png` |
| P2 (a11y) | `create.html`, `builder.html` | ۴ ورودی بی‌برچسب (`#catSearch`, `#rejNote`, `#msgText`, `#passNote`) | صفحه‌خوان | `aria-label` و `for=` | خزش بعد: `unlabeled=[]` | `pages-audit-after.json` |
| P2 (a11y) | `form.html` (نایافته/بسته/پیش‌نویس) | کارت خطای مسیر `div.title` بود → صفحه **بدون h1** | ساختار سرفصل | `<h1 class="title" id="unavailableTitle">` (استایل `.title` در `glass.css` اندازه/حاشیه را صریح تعیین می‌کند؛ ظاهر ثابت) | `smoke.test.mjs` 791 قبول؛ سرور تست `form.html?fid=missing-form` h1 دارد | کامیت `b8d1542` |
| P2 (a11y) | `offline.html` | تنها صفحهٔ بدون landmark `main` | ناوبری صفحه‌خوان | `div.wrap` → `main.wrap` (`sw.js` shell به `nora-v97` بامپ شده) | `service-worker-privacy.test.mjs` 20 قبول | کامیت `b8d1542` |
| پین‌های کش | همهٔ صفحه‌ها | — | کاربران قدیمی CSS/JS کهنه می‌گرفتند | `nora.css?v=101` (۱۱ صفحه)، `events-page.css?v=102`, `login.js?v=127`, `sw.js 'nora-v97'` + تست‌های `admin/support/events-page/service-worker-privacy` | Node 25/25 | کامیت `4da368b` |

---

## ۵. ممیزی دیداری و واکنش‌گرا

- پنج ویوپورت: **هیچ سرریز افقی** در هیچ صفحه‌ای (`scrollW == innerW` در ۲۷ مسیر × ۵ اندازه).
- موبایل (۳۶۰/۳۹۰): شیت‌های `sheet-m1..m4.png` — نوار پایین با safe-area، کارت‌ها، فرم‌ها و دیالوگ‌ها سالم؛ تنها نکتهٔ قدیمی: هم‌پوشانی جزئی هدر چسبان `builder.html` روی موبایل (ابزار پنل؛ تغییر نکرد).
- دسکتاپ (۱۲۸۰/۱۴۴۰): `sheet-desk.png` — خانه عمداً ستون مرکزی موبایل‌محور است (هویت فعلی نورا؛ تغییر نکرد)، رویدادها از پهنای بیشتر استفاده می‌کند، حساب مهمان و مطلب مرتب‌اند.
- تبلت (۷۶۸): فقط سنجه‌های خودکار (سرریز/خطا) ثبت شد؛ بازبینی چشمی تبلت انجام **نشد** (بخش ۸).
- حالت تیره (۳۹۰): خانه/رویدادها/مطلب/ورود/فرم سازگار (`sheet-dark.png`)؛ `404`/`offline`/`final-page-review` تم تیره ندارند (صفحه‌های مستقل سبک؛ تصمیم محصول، بخش ۸).
- تصویر شکسته: نهاد با `/uploads/does-not-exist-qa.webp` (دادهٔ تست) fallback حرف‌نگاره نشان می‌دهد، بدون شکستن چیدمان.
- `prefers-reduced-motion`: همهٔ صفحه‌ها بدون خطا و بدون انیمیشن اجباری.

## ۶. دسترس‌پذیری

اصلاح‌شده: حلقهٔ فوکوس جست‌وجوها، hit-area پین‌ها، ۴ برچسب ورودی، h1 فرم نایافته، `main` آفلاین. سالم از قبل: `alt` همهٔ تصاویر، نام همهٔ کنترل‌ها، یک h1 در هر صفحه، `aria-live` برای خطاهای فرم/ورود (در جریان‌ها دیده شد)، skip-link روی صفحه‌های عمومی اصلی. باقی‌مانده (بخش ۸): لوگوی پاورقی ۲۸px و لینک‌های متنی ۲۰px داخل کارت‌ها، چیپ‌های ۳۱px در create/builder، skip-link روی person/partner/login/account/support.

## ۷. امنیت، حریم خصوصی، SEO و سرعت

- متن کاربر/مدیر هرگز به‌صورت HTML رندر نمی‌شود (۹a–۹c روی سرور واقعی با payload واقعی).
- شناسه‌های URL فقط به محتوای منتشرشده می‌رسند؛ غیرعمومی → 404 + noindex؛ نشت `events/people/articles` بسته شد (P0 بالا).
- هیچ دادهٔ شخصی/کد/توکن در URL یا کنسول (کنسول همهٔ صفحه‌ها صفر خطا جز پروب‌های 401 مهمان).
- سرور منبع حقیقت: موفقیت فرم فقط پس از `2xx` واقعی (3d/4a)؛ ورود بدون سرویس پیامک هیچ کد جعلی نمی‌سازد (5b).
- `next=` بیرونی رد می‌شود (5e)؛ پشتیبانی بدون تماس منتشرشده هیچ لینک خارجی نمی‌سازد (7a)؛ لینک‌های خارجی نهادها با `rel="noopener"` (از مرحلهٔ قبل).
- SW: `nora-v97`؛ تست حریم خصوصی SW سبز (پاسخ‌های خصوصی کش نمی‌شوند؛ بعد از خروج محتوای حساب از کش نمی‌آید).
- SEO: عنوان/توضیح/canonical/og برای صفحه‌های عمومی بر پایهٔ محتوا (seo.py)؛ خصوصی‌ها noindex؛ 404 صحیح؛ `robots.txt`/`llms.txt` 200؛ sitemap در این محیط عمداً 503 (بدون base URL).
- سرعت: بارگیری محلی ۳۰–۱۶۰ms، ۱۰–۱۵ منبع، ۱۹۰–۵۱۵ KB؛ تنها outlier (۴۰۴، ۱٫۴۸ MB) به ۱۹۸ KB رسید. بهینه‌سازی دیگری که اثر اندازه‌پذیر داشته باشد یافت نشد.

---

## ۸. نیازمند تصمیم / پیشنهاد (انجام نشده، با دلیل)

| موضوع | چرا انجام نشد | گزینه‌ها / اثر |
|---|---|---|
| آیکون ✓ در توست مشترک `#toast` حتی برای پیام خطا (مثلاً «رونوشت خودکار ممکن نشد») | مؤلفهٔ مشترک `ui.js` در همهٔ صفحه‌ها؛ تغییر آن تصمیم طراحی است | افزودن نوع `error` به `toast()` با آیکون متفاوت (کم‌ریسک، ولی روی ۱۸ صفحه اثر دارد) |
| `og:image` ناهمگون: person ندارد، partner `icon-192`، بقیه `icon-512` | در `seo.py` سروری؛ انتخاب تصویر پیش‌فرض/تصویر فرد تصمیم محتوایی است | یکسان‌سازی روی `icon-512` یا استفاده از عکس فرد/لوگوی نهاد در صورت وجود |
| هدف‌های لمسی کوچک: `.flogo` پاورقی ۲۸px، لینک‌های متنی ۲۰px داخل کارت‌ها، چیپ‌های ۳۱px در create/builder | بزرگ‌کردن، فاصله‌گذاری و ظاهر کارت‌ها/پاورقی را تغییر می‌دهد | padding نامرئی مانند `.pinb::after` یا حداقل ۳۶px با بازطراحی جزئی |
| تم تیره برای `404`/`offline`/`final-page-review` | این سه صفحه عمداً مستقل و سبک‌اند (بدون `glass.css` کامل/SW) | افزودن متغیرهای تیره (کوچک) یا پذیرش وضعیت فعلی |
| skip-link روی person/partner/login/account/support | الگوی فعلی فقط روی صفحه‌های محتوایی بلند است | افزودن همان الگوی `home.html` (کم‌ریسک) |
| مقصد «قوانین» در پاورقی ورود | صفحهٔ قوانین/حریم خصوصی مستقل وجود ندارد؛ متن سیاست تصمیم سازمان است | ساخت صفحهٔ سیاست یا حذف لینک تا آماده شدن متن |
| لینک fixture پنهان `event.html?id=e5` در DOM `form.html` (نامرئی، فقط در حالت نایافته در DOM است) | نمونهٔ محلی `SAMPLE` برای حالت fixture؛ به کاربر نشان داده نمی‌شود | رندر لینک‌های پایانی فقط از تعریف سروری فرم |
| `main` landmark در `form.html` | `.wrap > header` و چندین selector وابسته؛ ریسک رگرسیون چیدمان فرم چندمرحله‌ای | `role="main"` روی `.wrap` یا بازبینی selectorها در مرحلهٔ جدا |
| خط لاگ سرور `❌ خطای پایگاه داده: OperationalError` هنگام ساخت بلیت | ریشه‌یابی شد: رندر بلیت وب از `bale-bot/nora_bot/form_ticket_image.py` → `config.org_name()` → **پایگاه ربات** را می‌خواند؛ در محیط تست جدول تنظیمات ربات وجود ندارد → نام پیش‌فرض استفاده می‌شود (بلیت ساخته شد؛ جریان 3c سبز). در تولید تک‌میزبان، DB ربات موجود است | جداکردن نام سازمان بلیت از DB ربات (تنظیم سمت وب) — تغییر معماری کوچک، خارج از این ممیزی |
| بازبینی چشمی تبلت ۷۶۸ و ۱۴۴۰ کامل | فقط سنجه‌های خودکار گرفته شد (زمان) | در صورت نیاز با همان ابزار و `SHOT_VIEWPORTS` گسترده |
| قابلیت‌های نقشهٔ راه (امتیازدهی، دعوت دوستان، کیف پول واقعی، حذف حساب) | نیازمند API/سیاست؛ طبق قاعدهٔ §۹ ساخته نشد | پیشنهادهای جداگانه در گزارش‌های قبلی |

---

## ۹. فهرست صفحه‌ها/مسیرهایی که بررسی شدند (کامل)

`/`, `/index.html`, `/home.html`(+`#articles/#teachers/#partners/#notice`), `/events.html`(+`?status=past|upcoming`, `#list/#cat/#lib`), `/event.html?id=qa-ev-1|qa-ev-2|qa-ev-past|qa-ev-xss|نامعتبر`, `/post.html?id=np-qa-1|np-qa-2|np-qa-xss|نامعتبر`, `/person.html?id=qa-p1|qa-p-xss|نامعتبر`, `/partner.html?id=qa-partner-1|qa%20partner%2F2%20%C3%BC|qa-partner-broken-logo|qa-partner-xss|نامعتبر`, `/login.html`(+`?mode=server|staff`, `&next=`), `/account.html`(+`#events/#forms/#profile/#payments/#book/#acc-20`), `/form.html?fid=<منتشرشده>&kind=reg`, `/form.html?fid=نامعتبر`, `/form.html`, `/form.html?preview=1`, `/final-page-review.html`(+`?fid=`), `/support.html`(+`#reader`), `/404.html`, `/no-such-page.html`, `/offline.html`, `/create.html`(+`?auth=1&back=builder.html`), `/builder.html`, `/loading-preview.html`, `/nora-pay-preview.html`, `/admin.html`(فقط به‌عنوان مقصد لینک؛ پنل خارج از این ممیزی), `/robots.txt`, `/llms.txt`, `/sitemap.xml`, `/404-art.webp`.

---

## ۱۰. رگرسیون و شواهد

| مجموعه | قبل از تغییر | بعد از تغییر | لاگ |
|---|---|---|---|
| pytest بک‌اند (`backend/tests`) | 222 passed / 4 skipped (مرحلهٔ قبل) + تست تازه **3 failed** | **225 passed, 4 skipped** | `logs/pytest-read-boundary-red.log`, `logs/pytest-user-pages-2026-10-18.log` |
| mypy (`backend/mypy.ini`) | تمیز | **تمیز** | `logs/mypy-user-pages-2026-10-18.log` |
| Node (`tools/run-unit-tests.cjs`, ۲۵ مجموعه) | 25/25 | **25/25** (+ بازاجرای `post` 103، `asset-audit` 0 fail، `server` 0 fail، `smoke` 791، `service-worker-privacy` 20 پس از آخرین ویرایش‌ها) | `logs/unit-tests-user-pages-2026-10-18.log` |
| جریان‌های Playwright روی سرور تست | 42/47 | **53/53** | `logs/flows-audit-run1.log`, `logs/flows-audit-run2.log`, `flows-results-run2.json` |
| خزش صفحه‌ها (۲۷ مسیر × ۵ ویوپورت) | `pages-audit-before.json` | `pages-audit-after.json` (۱۰ صفحهٔ تغییریافته) | `logs/pages-audit-run1.log`, `logs/pages-audit-after.log` |

پوشهٔ شواهد: `Final-Delivery/reports/evidence-user-pages-audit-2026-10-18/` — `logs/` (۸ لاگ کامل؛ چون `*.log` در `.gitignore` است با `git add -f` اضافه شدند)، `shots/before|after|flows|sheets/`, `tools/` (دو اسکریپت ممیزی)، `README.md`. اسکن راز: رمز مالک تست، pepper، `Set-Cookie`، توکن و نشست در هیچ فایلی نیست؛ تنها شمارهٔ موجود `09120000000` شمارهٔ ساختگیِ اسکریپت تست است.

تغییرات سالم مراحل قبل (تست‌های نهادها، نگه‌داشت ردیف‌های غیرعمومی، صفحهٔ نهاد، خانه) همگی سبز ماندند.

---

## ۱۱. فایل‌های تغییریافته

- بک‌اند: `backend/site_content.py`, `backend/app.py`, `backend/tests/test_partner_retention.py`.
- رابط کاربر: `home.html`, `nora.css`, `events-page.css`, `login.html`, `login.js`, `final-page-review.html`, `form.html`, `post.html`, `create.html`, `builder.html`, `404.html`, **`404-art.webp` (جدید)**, `offline.html`, `sw.js`, پین `nora.css?v=101` در `account/admin/event/events/loading-preview/offline/partner/person/post/support.html`.
- تست‌ها: `post.test.mjs` (+۴)، `admin.test.mjs`, `support.test.mjs`, `events-page.test.mjs`, `service-worker-privacy.test.mjs` (پین‌ها).
- گزارش/شواهد: همین فایل + پوشهٔ شواهد.

## ۱۲. وضعیت نهایی Git

- شاخه `arena/840de336-strix`؛ کامیت‌ها: `e977786`, `4da368b`, `31e6b52`, `b8d1542` + `de18a23` (گزارش/شواهد).
- همه فقط به همین شاخه push شده‌اند؛ PR #1 **باز** مانده؛ هیچ merge/release/deploy انجام نشده.
- محدودیت‌ها: همهٔ آزمون‌ها روی سرور تست محلی با دادهٔ تست؛ هیچ آزمونی روی دامنهٔ زنده، پیامک واقعی، بله یا پرداخت واقعی انجام نشده است.
